"""
Reddit API client with AGGREGATED LLM extraction.
Sends 20-40 posts per request (60-80K tokens) with concise aggregated output.
"""
from typing import Any
from collections import Counter
from ticker_validator import fetch_valid_tickers
from llm_extractor_aggregated import extract_tickers_aggregated
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
    Analyze subreddit using AGGREGATED batching (60-80K tokens per request).
    """
    reddit = get_reddit_client()
    subreddit = reddit.subreddit(subreddit_name)
    valid_tickers = fetch_valid_tickers()
    
    ticker_counter: Counter = Counter()
    
    time_filter = {'day': 'day', 'week': 'week', 'month': 'month'}.get(timeframe, 'day')
    
    print(f"  Fetching {limit} posts from r/{subreddit_name}...")
    
    # Phase 1: Collect posts with pre-filtering
    all_posts = []
    top_comments_collected = []
    filtered_flairs = 0
    filtered_low_score = 0
    filtered_no_tickers = 0
    
    SKIP_FLAIRS = ['gain', 'loss', 'gain/loss', 'gains', 'losses', 'meme']
    
    try:
        for post in subreddit.top(time_filter=time_filter, limit=limit * 3):
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
            
            if not should_analyze_post(post, min_score=10):
                filtered_no_tickers += 1
                continue
            
            all_posts.append(post)
            
            # Collect comments
            post.comment_sort = 'top'
            post.comments.replace_more(limit=0)
            
            post_top_comments = post.comments.list()[:comments_per_post]
            
            for comment in post_top_comments:
                if len(comment.body) > 20:
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
    
    # Phase 2: AGGREGATED POST ANALYSIS (60-80K tokens per request)
    print(f"  Creating aggregated batches (60-80K tokens each)...")
    
    post_texts = []
    for post in all_posts:
        text = f"TITLE: {post.title}\n\nBODY: {post.selftext}"
        if len(text.strip()) > 10:
            post_texts.append(text)
    
    # Batch to 60-80K tokens (leaving room for reasoning)
    post_batches = batch_posts_by_tokens(post_texts, max_tokens=75000)
    
    if post_batches:
        total_tokens_estimate = sum(estimate_token_count(p) for p in post_texts)
        print(f"  Created {len(post_batches)} batches (~{total_tokens_estimate:,} tokens total)")
    
    for batch_idx, batch in enumerate(post_batches):
        if model_manager.check_budget() <= 0:
            print(f"⚠️  Budget exhausted at batch {batch_idx+1}/{len(post_batches)}")
            break
        
        batch_tokens = sum(estimate_token_count(p) for p in batch)
        print(f"    Batch {batch_idx+1}/{len(post_batches)}: {len(batch)} posts, ~{batch_tokens:,} tokens...", end='', flush=True)
        
        # Send batch and get AGGREGATED result
        result = extract_tickers_aggregated(batch, model_manager, valid_tickers)
        
        if not result or not result.get('tickers'):
            print(f" no results")
            continue
        
        # Update counter with aggregated mentions
        for ticker, data in result['tickers'].items():
            mentions = data.get('mentions', 1)
            ticker_counter[ticker] += mentions
        
        print(f" ✓ Found {len(result['tickers'])} tickers (saved {len(batch)-1} calls)")
    
    print(f"  ✓ Analyzed {len(post_texts)} posts in {len(post_batches)} API requests")
    
    # Phase 3: AGGREGATED COMMENT ANALYSIS
    sorted_comments = sorted(
        top_comments_collected,
        key=lambda c: c['score'],
        reverse=True
    )[:global_top_comments]
    
    # Filter comments
    quality_comments, filter_stats = filter_comments(sorted_comments, min_length=40, verbose=True)
    
    if quality_comments:
        print(f"  Analyzing {len(quality_comments)} quality comments...")
        
        # Batch comments to 60-80K tokens
        comment_texts = [c['body'] for c in quality_comments]
        comment_batches = batch_posts_by_tokens(comment_texts, max_tokens=75000)
        
        for batch_idx, batch in enumerate(comment_batches):
            if model_manager.check_budget() <= 0:
                break
            
            batch_tokens = sum(estimate_token_count(c) for c in batch)
            print(f"    Comment batch {batch_idx+1}: {len(batch)} comments, ~{batch_tokens:,} tokens...", end='', flush=True)
            
            result = extract_tickers_aggregated(batch, model_manager, valid_tickers)
            
            if result and result.get('tickers'):
                for ticker, data in result['tickers'].items():
                    mentions = data.get('mentions', 1)
                    ticker_counter[ticker] += mentions
                
                print(f" ✓ Found {len(result['tickers'])} tickers")
            else:
                print(f" no results")
    
    print(f"  📊 Budget: {model_manager.get_stats()}")
    
    return ticker_counter


# Keep original function name for compatibility
def get_ticker_sentiment_llm(
    subreddit_name: str,
    ticker: str,
    limit: int = 50,
    model_manager: Any = None
) -> list:
    """Get sentiment using aggregated analysis."""
    reddit = get_reddit_client()
    subreddit = reddit.subreddit(subreddit_name)
    
    valid_tickers = fetch_valid_tickers()
    posts = []
    
    try:
        SKIP_FLAIRS = ['gain', 'loss', 'gain/loss', 'gains', 'losses', 'meme']
        
        for post in subreddit.search(ticker, time_filter='week', limit=limit * 2):
            if model_manager.check_budget() <= 0:
                break
            
            flair = (post.link_flair_text or '').lower()
            if any(skip_flair in flair for skip_flair in SKIP_FLAIRS):
                continue
                
            text = f"{post.title}\n\n{post.selftext}"
            
            posts.append({
                'id': post.id,
                'title': post.title,
                'text': text,
                'score': post.score,
                'url': post.url,
            })
    
    except Exception as e:
        print(f"Error searching: {e}")
    
    return posts

