"""
Pre-filter posts before LLM analysis to save API requests.
Only process posts likely to contain tickers with good engagement.
"""
import re

def likely_has_ticker(text: str) -> bool:
    """
    Quick check if text likely contains stock tickers.
    Much faster than LLM, filters out irrelevant posts.
    
    Args:
        text: Post title + body text
    
    Returns:
        True if text likely contains tickers
    """
    if not text or len(text) < 10:
        return False
    
    # Check for $ symbols (common ticker notation)
    if '$' in text and re.search(r'\$[A-Z]{1,5}\b', text):
        return True
    
    # Check for all-caps words 1-5 letters (likely tickers)
    # But avoid common words
    COMMON_WORDS = {
        'I', 'A', 'IT', 'IS', 'OR', 'SO', 'DO', 'GO', 'TO', 'BE', 'WE', 'HE', 'ME',
        'US', 'UP', 'AT', 'BY', 'IN', 'ON', 'NO', 'MY', 'AM', 'AN', 'AS', 'IF',
        'THE', 'AND', 'FOR', 'NOT', 'BUT', 'CAN', 'ALL', 'ARE', 'WAS', 'HAS',
        'HIS', 'HER', 'ITS', 'OUR', 'OUT', 'NEW', 'NOW', 'OLD', 'ONE', 'TWO',
        'WHY', 'HOW', 'WHO', 'MAY', 'WAY', 'DAY', 'GET', 'GOT', 'HAD', 'HAS',
        'WILL', 'YEAR', 'WEEK', 'TIME', 'JUST', 'LIKE', 'MAKE', 'TAKE', 'LOOK',
        'KNOW', 'THINK', 'WANT', 'NEED', 'GOOD', 'MUCH', 'MORE', 'VERY', 'WELL',
        'ALSO', 'BACK', 'DOWN', 'EVEN', 'BEEN', 'FROM', 'HERE', 'ONLY', 'OVER',
        'THAN', 'THEN', 'THEM', 'THEY', 'THIS', 'THAT', 'WHAT', 'WHEN', 'WITH',
        'YOUR', 'HAVE', 'INTO', 'SOME', 'SAID', 'EACH', 'COME', 'MADE', 'MOST',
        'LONG', 'DOES', 'SUCH', 'BOTH', 'MANY', 'MUST', 'CALL', 'NEXT', 'EVER',
        'ONCE', 'DD', 'TA', 'FD', 'ATH', 'ATL', 'IPO', 'ETF', 'CEO', 'CFO',
        'WSB', 'IMO', 'TBH', 'IMO', 'LOL', 'WTF', 'FYI', 'ASAP', 'FOMO', 'YOLO'
    }
    
    # Find potential tickers (1-5 caps letters)
    potential_tickers = re.findall(r'\b[A-Z]{1,5}\b', text)
    
    # Count non-common-word tickers
    ticker_count = sum(1 for t in potential_tickers if t not in COMMON_WORDS)
    
    # If we found 1+ likely ticker, probably worth analyzing
    return ticker_count >= 1


def should_analyze_post(post, min_score: int = 10) -> bool:
    """
    Pre-filter to determine if post is worth LLM analysis.
    
    Args:
        post: Reddit post object
        min_score: Minimum upvote score (default: 10)
    
    Returns:
        True if post should be analyzed
    """
    # Check upvote threshold
    if post.score < min_score:
        return False
    
    # Check if likely has tickers
    text = f"{post.title}\n\n{post.selftext}"
    return likely_has_ticker(text)


def estimate_token_count(text: str) -> int:
    """
    Rough estimate of token count (1 token ≈ 4 characters).
    
    Args:
        text: Text to estimate
    
    Returns:
        Estimated token count
    """
    return len(text) // 4


def batch_posts_by_tokens(posts: list, max_tokens: int = 98000) -> list:
    """
    Batch posts together to maximize token usage per API call.
    
    Args:
        posts: List of post texts
        max_tokens: Maximum tokens per batch (default: 98K, maximizing 100K+ context windows)
    
    Returns:
        List of batches, where each batch is a list of post texts
    """
    batches = []
    current_batch = []
    current_tokens = 0
    
    for post in posts:
        post_tokens = estimate_token_count(post)
        
        # If adding this post would exceed limit, start new batch
        if current_tokens + post_tokens > max_tokens and current_batch:
            batches.append(current_batch)
            current_batch = []
            current_tokens = 0
        
        current_batch.append(post)
        current_tokens += post_tokens
    
    # Add remaining batch
    if current_batch:
        batches.append(current_batch)
    
    return batches

