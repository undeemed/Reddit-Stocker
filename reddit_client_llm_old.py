"""
Reddit API client with LLM-enhanced extraction.
Uses Reddit's native comment sorting and batch analysis for efficiency.
"""
from typing import Any
from collections import Counter
from ticker_validator import fetch_valid_tickers
from llm_extractor import extract_tickers_with_llm, extract_tickers_batch
from reddit_client import get_reddit_client
from comment_filter import filter_comments
from post_filter import should_analyze_post, batch_posts_by_tokens, estimate_token_count


def get_subreddit_tickers_llm(
    subreddit_name: str,
    timeframe: str,
    limit: int = 100,
    comments_per_post: int = 5,
    global_top_comments: int = 50,
    batch_size: int = 50,
    model_manager: Any = None
) -> Counter:
    """
    Analyze posts + top comments using Reddit's native sorting.
    
    Args:
        subreddit_name: Subreddit to analyze
        timeframe: 'day', 'week', or 'month'
        limit: Number of posts to fetch
        comments_per_post: Top N comments to fetch per post (Reddit-sorted)
        global_top_comments: After collection, analyze top X globally
        batch_size: Comments to batch per LLM request
        model_manager: MultiModelManager instance
    
    Returns:
        Counter object with ticker mention counts
    """
    reddit = get_reddit_client()
    subreddit = reddit.subreddit(subreddit_name)
    valid_tickers = fetch_valid_tickers()
    
    ticker_counter: Counter = Counter()
    
    time_filter = {'day': 'day', 'week': 'week', 'month': 'month'}.get(timeframe, 'day')
    
    print(f"  Fetching {limit} posts from r/{subreddit_name}...")
    
    # Phase 1: Collect posts and top comments with pre-filtering
    all_posts = []
    top_comments_collected = []
    filtered_flairs = 0
    filtered_low_score = 0
    filtered_no_tickers = 0
    
    # Flairs to skip (low-value content)
    SKIP_FLAIRS = ['gain', 'loss', 'gain/loss', 'gains', 'losses', 'meme']
    
    try:
        for post in subreddit.top(time_filter=time_filter, limit=limit * 3):  # Fetch 3x to compensate for filtering
            if len(all_posts) >= limit:
                break
            
            # Filter by flair
            flair = (post.link_flair_text or '').lower()
            if any(skip_flair in flair for skip_flair in SKIP_FLAIRS):
                filtered_flairs += 1
                continue
            
            # Pre-filter: Check upvotes and likely ticker presence
            if post.score < 10:
                filtered_low_score += 1
                continue
            
            text = f"{post.title}\n\n{post.selftext}"
            if not should_analyze_post(post, min_score=10):
                filtered_no_tickers += 1
                continue
            
            all_posts.append(post)
            
            # Use Reddit's native sorting!
            post.comment_sort = 'top'
            post.comments.replace_more(limit=0)
            
            # Get top N comments per post (already sorted by Reddit!)
            post_top_comments = post.comments.list()[:comments_per_post]
            
            for comment in post_top_comments:
                if len(comment.body) > 20:  # Filter trivial comments
                    top_comments_collected.append({
                        'body': comment.body,
                        'score': comment.score,
                        'post_id': post.id
                    })
    
    except Exception as e:
        print(f"Error fetching posts: {e}")
        return ticker_counter
    
    # Report filtering stats
    total_filtered = filtered_flairs + filtered_low_score + filtered_no_tickers
    if total_filtered > 0:
        print(f"  📊 Pre-filter: {len(all_posts)} posts kept, {total_filtered} filtered")
        print(f"     └─ Flair: {filtered_flairs}, Low score: {filtered_low_score}, No tickers: {filtered_no_tickers}")
    print(f"  Collected {len(all_posts)} posts, {len(top_comments_collected)} comments")
    
    # Phase 2a: Batch analyze posts to maximize token usage
    print(f"  Batching posts for efficient LLM analysis...")
    
    # Prepare post texts
    post_texts = []
    for post in all_posts:
        text = f"{post.title}\n\n{post.selftext}"
        if len(text.strip()) > 10:
            post_texts.append(text)
    
    # Batch posts by token limit (~98K tokens per batch to maximize 100K+ context windows)
    post_batches = batch_posts_by_tokens(post_texts, max_tokens=98000)
    
    print(f"  Created {len(post_batches)} batches (avg {len(post_texts)//len(post_batches) if post_batches else 0} posts/batch)")
    
    posts_analyzed = 0
    for batch_idx, batch in enumerate(post_batches):
        if model_manager.check_budget() <= 0:
            print(f"⚠️  Budget exhausted at batch {batch_idx}/{len(post_batches)}")
            break
        
        # Send entire batch in one request
        results = extract_tickers_batch(batch, model_manager, valid_tickers)
        if any(r.get('budget_exhausted') for r in results):
            break
        
        for result in results:
            if result['tickers']:
                ticker_counter.update(result['tickers'])
                posts_analyzed += 1
        
        print(f"    Batch {batch_idx+1}/{len(post_batches)}: {len(batch)} posts in 1 request (saved {len(batch)-1} calls)")
    
    print(f"  Analyzed {posts_analyzed} posts in {batch_idx+1 if post_batches else 0} API requests")
    
    # Phase 2b: Re-sort comments globally and take top X
    sorted_comments = sorted(
        top_comments_collected,
        key=lambda c: c['score'],
        reverse=True
    )[:global_top_comments]
    
    # Phase 2b-2: Filter out low-quality comments BEFORE LLM
    quality_comments, filter_stats = filter_comments(sorted_comments, min_length=40, verbose=True)
    
    print(f"  Analyzing top {len(quality_comments)} quality comments (filtered out memes/spam)")
    
    # Phase 2c: Batch analyze comments
    batch = []
    batch_texts = []
    comments_analyzed = 0
    
    for comment in quality_comments:
        if model_manager.check_budget() <= 0:
            break
        
        if len(comment['body']) < 300:  # Short comment - batch it
            batch.append(comment)
            batch_texts.append(comment['body'])
            
            if len(batch) >= batch_size:
                # Batch LLM request
                results = extract_tickers_batch(batch_texts, model_manager, valid_tickers)
                if any(r.get('budget_exhausted') for r in results):
                    break
                
                for result in results:
                    if result['tickers']:
                        ticker_counter.update(result['tickers'])
                        comments_analyzed += 1
                
                print(f"    Batched {len(batch)} comments in 1 request (saved {len(batch)-1} calls)")
                batch = []
                batch_texts = []
        
        else:  # Long comment - analyze separately
            result = extract_tickers_with_llm(comment['body'], model_manager, valid_tickers)
            if result.get('budget_exhausted'):
                break
            if result['tickers']:
                ticker_counter.update(result['tickers'])
                comments_analyzed += 1
    
    # Process remaining batch
    if batch and model_manager.check_budget() > 0:
        results = extract_tickers_batch(batch_texts, model_manager, valid_tickers)
        for result in results:
            if result['tickers']:
                ticker_counter.update(result['tickers'])
                comments_analyzed += 1
    
    print(f"  Analyzed {comments_analyzed} comments")
    print(f"  📊 Budget: {model_manager.get_stats()}")
    
    return ticker_counter


def get_ticker_sentiment_llm(
    subreddit_name: str,
    ticker: str,
    limit: int = 50,
    model_manager: Any = None
) -> list:
    """
    Get posts mentioning a ticker with LLM-extracted context.
    
    Args:
        subreddit_name: Name of the subreddit
        ticker: Stock ticker to search for
        limit: Maximum number of posts to fetch
        model_manager: MultiModelManager instance
    
    Returns:
        List of posts with LLM-extracted context
    """
    reddit = get_reddit_client()
    subreddit = reddit.subreddit(subreddit_name)
    
    valid_tickers = fetch_valid_tickers()
    posts = []
    
    try:
        # Flairs to skip
        SKIP_FLAIRS = ['gain', 'loss', 'gain/loss', 'gains', 'losses', 'meme']
        
        # Search for ticker
        for post in subreddit.search(ticker, time_filter='week', limit=limit * 2):
            if model_manager.check_budget() <= 0:
                break
            
            # Filter by flair
            flair = (post.link_flair_text or '').lower()
            if any(skip_flair in flair for skip_flair in SKIP_FLAIRS):
                continue
                
            text = f"{post.title}\n\n{post.selftext}"
            
            # Use LLM to verify and extract context
            result = extract_tickers_with_llm(text, model_manager, valid_tickers)
            
            if ticker in result['tickers']:
                posts.append({
                    'id': post.id,
                    'title': post.title,
                    'text': text,
                    'score': post.score,
                    'url': post.url,
                    'llm_context': result['context'].get(ticker, '')
                })
        
        # Also check hot posts
        for post in subreddit.hot(limit=limit):
            if model_manager.check_budget() <= 0:
                break
                
            text = f"{post.title}\n\n{post.selftext}"
            result = extract_tickers_with_llm(text, model_manager, valid_tickers)
            
            if ticker in result['tickers']:
                if not any(p['id'] == post.id for p in posts):
                    posts.append({
                        'id': post.id,
                        'title': post.title,
                        'text': text,
                        'score': post.score,
                        'url': post.url,
                        'llm_context': result['context'].get(ticker, '')
                    })
    
    except Exception as e:
        print(f"Error fetching ticker posts from r/{subreddit_name}: {e}")
    
    return posts
