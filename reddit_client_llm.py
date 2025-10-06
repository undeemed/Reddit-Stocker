"""
Reddit API client with LLM-enhanced extraction.
Uses Reddit's native comment sorting and batch analysis for efficiency.
"""
from typing import Any
from collections import Counter
from ticker_validator import fetch_valid_tickers
from llm_extractor import extract_tickers_with_llm, extract_tickers_batch
from reddit_client import get_reddit_client


def get_subreddit_tickers_llm(
    subreddit_name: str,
    timeframe: str,
    limit: int = 100,
    comments_per_post: int = 5,
    global_top_comments: int = 50,
    batch_size: int = 5,
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
    
    # Phase 1: Collect posts and top comments
    all_posts = []
    top_comments_collected = []
    
    try:
        for post in subreddit.top(time_filter=time_filter, limit=limit):
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
    
    print(f"  Collected {len(all_posts)} posts, {len(top_comments_collected)} comments")
    
    # Phase 2a: Analyze ALL posts with LLM
    posts_analyzed = 0
    for post in all_posts:
        if model_manager.check_budget() <= 0:
            print(f"⚠️  Budget exhausted at {posts_analyzed} posts")
            break
        
        text = f"{post.title}\n\n{post.selftext}"
        if len(text.strip()) > 10:
            result = extract_tickers_with_llm(text, model_manager, valid_tickers)
            if result.get('budget_exhausted'):
                break
            if result['tickers']:
                ticker_counter.update(result['tickers'])
                posts_analyzed += 1
    
    print(f"  Analyzed {posts_analyzed} posts")
    
    # Phase 2b: Re-sort comments globally and take top X
    sorted_comments = sorted(
        top_comments_collected,
        key=lambda c: c['score'],
        reverse=True
    )[:global_top_comments]
    
    print(f"  Analyzing top {len(sorted_comments)} comments globally (highest upvotes)")
    
    # Phase 2c: Batch analyze comments
    batch = []
    batch_texts = []
    comments_analyzed = 0
    
    for comment in sorted_comments:
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
        # Search for ticker
        for post in subreddit.search(ticker, time_filter='week', limit=limit):
            if model_manager.check_budget() <= 0:
                break
                
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
