"""Reddit API client for fetching posts and comments."""
import praw
import re
from typing import Set, Optional
from collections import Counter
from config import (
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    REDDIT_USER_AGENT,
    TICKER_PATTERN,
    COMMON_WORDS
)
from ticker_validator import fetch_valid_tickers


def get_reddit_client() -> praw.Reddit:
    """Create and return a Reddit API client."""
    if not REDDIT_CLIENT_ID or not REDDIT_CLIENT_SECRET:
        raise ValueError(
            "Reddit API credentials not found. "
            "Please set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in .env file"
        )
    
    return praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT
    )


def extract_tickers(text: str, valid_tickers: Optional[Set[str]] = None) -> Set[str]:
    """
    Extract valid stock tickers from text.
    
    Args:
        text: Text to extract tickers from
        valid_tickers: Set of valid ticker symbols (fetched if not provided)
        
    Returns:
        Set of valid stock tickers
    """
    # Fetch valid tickers if not provided
    if valid_tickers is None:
        valid_tickers = fetch_valid_tickers()
    
    # Find all potential tickers
    potential_tickers = set(re.findall(TICKER_PATTERN, text))
    
    # Filter: remove common words AND validate against real stock symbols
    tickers = (potential_tickers - COMMON_WORDS) & valid_tickers
    
    return tickers


def get_subreddit_tickers(subreddit_name: str, timeframe: str, limit: int = 100) -> Counter:
    """
    Get stock ticker mentions from a subreddit.
    
    Args:
        subreddit_name: Name of the subreddit
        timeframe: 'day', 'week', or 'month'
        limit: Maximum number of posts to fetch
        
    Returns:
        Counter object with ticker mention counts
    """
    reddit = get_reddit_client()
    subreddit = reddit.subreddit(subreddit_name)
    
    ticker_counter: Counter = Counter()
    
    # Fetch valid tickers once (cached for 24 hours)
    valid_tickers = fetch_valid_tickers()
    
    # Map timeframe to Reddit time filter
    time_filters = {
        'day': 'day',
        'week': 'week',
        'month': 'month'
    }
    
    time_filter = time_filters.get(timeframe, 'day')
    
    try:
        # Get hot posts from the specified timeframe
        for post in subreddit.top(time_filter=time_filter, limit=limit):
            # Extract tickers from post title and body
            text = f"{post.title} {post.selftext}"
            tickers = extract_tickers(text, valid_tickers)
            ticker_counter.update(tickers)
            
            # Extract tickers from top comments
            try:
                post.comments.replace_more(limit=0)  # Skip "load more comments"
                for comment in post.comments.list()[:50]:  # Limit to top 50 comments
                    comment_tickers = extract_tickers(comment.body, valid_tickers)
                    ticker_counter.update(comment_tickers)
            except Exception:
                continue  # Skip if comments fail to load
                
    except Exception as e:
        print(f"Error fetching from r/{subreddit_name}: {e}")
    
    return ticker_counter


def get_ticker_posts(subreddit_name: str, ticker: str, limit: int = 50) -> list:
    """
    Get posts mentioning a specific ticker from a subreddit.
    
    Args:
        subreddit_name: Name of the subreddit
        ticker: Stock ticker to search for
        limit: Maximum number of posts to fetch
        
    Returns:
        List of posts containing the ticker
    """
    reddit = get_reddit_client()
    subreddit = reddit.subreddit(subreddit_name)
    
    # Fetch valid tickers once
    valid_tickers = fetch_valid_tickers()
    
    posts = []
    
    try:
        # Search for ticker in the subreddit (past week)
        for post in subreddit.search(ticker, time_filter='week', limit=limit):
            # Verify ticker is actually mentioned
            text = f"{post.title} {post.selftext}"
            if ticker in extract_tickers(text, valid_tickers):
                posts.append({
                    'id': post.id,
                    'title': post.title,
                    'text': text,
                    'score': post.score,
                    'url': post.url
                })
        
        # Also check hot posts for mentions
        for post in subreddit.hot(limit=limit):
            text = f"{post.title} {post.selftext}"
            if ticker in extract_tickers(text, valid_tickers):
                # Avoid duplicates
                if not any(p['id'] == post.id for p in posts):
                    posts.append({
                        'id': post.id,
                        'title': post.title,
                        'text': text,
                        'score': post.score,
                        'url': post.url
                    })
    
    except Exception as e:
        print(f"Error fetching ticker posts from r/{subreddit_name}: {e}")
    
    return posts

