"""
Comment quality filter to skip meme/low-value content before LLM analysis.
Saves API requests by filtering out garbage comments.

Also includes post flair filtering to skip Gain/Loss/YOLO posts.
"""
import re

# Meme phrases that indicate low-value content
MEME_PHRASES = [
    r'\b(to the moon|moon|rocket|wen lambo|lambo)\b',
    r'\b(yolo|fomo|hodl|diamond hands?|paper hands?)\b',
    r'\b(tendies|stonks?|apes? together strong|this is the way)\b',
    r'\b(buy the dip|dip|rip|btfd)\b',
    r'\b(pump it|dump it|shill|bag holder)\b',
    r'\b(wsb|retard|regard|autis[tm])\b',
    r'\b(brrr|printer go brrr)\b',
    r'^\s*f+\s*$',  # Just "F" or "FFFF"
    r'^\s*nice\s*$',  # Just "nice"
    r'^\s*this\s*$',  # Just "this"
]

# Low-effort patterns
LOW_EFFORT_PATTERNS = [
    r'^[🚀💎🙌📈📉💰🤑😂😭👍👎]+$',  # Pure emoji
    r'^\s*lol\s*$',
    r'^\s*lmao\s*$',
    r'^\s*omg\s*$',
    r'^\s*wow\s*$',
    r'^\s*same\s*$',
    r'^\s*agreed?\s*$',
    r'^\s*\+1\s*$',
]

# High-value indicators (these are GOOD - keep these comments)
VALUE_INDICATORS = [
    r'\b(earnings?|revenue|profit|loss|eps|p/e|valuation)\b',
    r'\b(analyst|target|price target|upgrade|downgrade)\b',
    r'\b(fundamental|technical|chart|support|resistance)\b',
    r'\b(news|announced|report|filing|sec|10-k|10-q)\b',
    r'\b(management|ceo|cfo|guidance|outlook)\b',
    r'\b(competitor|competition|market share|growth)\b',
    r'\b(quarter|q[1-4]|fy20\d\d|annual)\b',
    r'\b(debt|cash flow|balance sheet|assets)\b',
    r'\b(dividend|yield|payout)\b',
    r'\$\d+',  # Dollar amounts
    r'\d+%',  # Percentages
    r'\b(bought|sold|position|shares?|entry|exit)\b',
]


def is_quality_comment(text: str, min_length: int = 40) -> bool:
    """
    Check if comment is worth analyzing with LLM.
    
    Args:
        text: Comment text
        min_length: Minimum character length (default: 40)
    
    Returns:
        True if comment should be analyzed, False if it should be skipped
    """
    if not text or len(text.strip()) < min_length:
        return False
    
    text_lower = text.lower()
    
    # Skip pure emoji/low-effort
    for pattern in LOW_EFFORT_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return False
    
    # Check for high-value indicators first (override meme detection)
    has_value = any(re.search(pattern, text_lower, re.IGNORECASE) 
                    for pattern in VALUE_INDICATORS)
    
    if has_value:
        return True  # Has fundamentals/DD - keep it
    
    # Count meme phrases
    meme_count = sum(1 for pattern in MEME_PHRASES 
                     if re.search(pattern, text_lower, re.IGNORECASE))
    
    # If >30% of content is memes, skip it
    word_count = len(text_lower.split())
    if word_count > 0 and meme_count / word_count > 0.3:
        return False
    
    # Check emoji ratio
    emoji_count = sum(1 for c in text if ord(c) > 127000)  # Unicode emoji range
    char_count = len(text)
    if char_count > 0 and emoji_count / char_count > 0.2:  # >20% emojis
        return False
    
    # Default: keep it
    return True


def should_skip_post_flair(flair: str) -> bool:
    """
    Check if post flair indicates low-value content (Gain/Loss/YOLO posts).
    
    Args:
        flair: Post flair text (case-insensitive)
    
    Returns:
        True if post should be skipped
    """
    if not flair:
        return False
    
    SKIP_FLAIRS = ['gain', 'loss', 'gain/loss', 'gains', 'losses', 'meme']
    flair_lower = flair.lower()
    
    return any(skip_flair in flair_lower for skip_flair in SKIP_FLAIRS)


def filter_comments(comments: list, min_length: int = 40, verbose: bool = False) -> tuple:
    """
    Filter list of comments, return (quality_comments, stats).
    
    Args:
        comments: List of comment dicts with 'body' field
        min_length: Minimum character length
        verbose: Print filtering stats
    
    Returns:
        (filtered_comments, stats_dict)
    """
    quality_comments = []
    filtered_count = 0
    
    for comment in comments:
        if is_quality_comment(comment.get('body', ''), min_length):
            quality_comments.append(comment)
        else:
            filtered_count += 1
    
    stats = {
        'total': len(comments),
        'kept': len(quality_comments),
        'filtered': filtered_count,
        'filter_rate': filtered_count / len(comments) if comments else 0
    }
    
    if verbose and comments:
        print(f"  📊 Comment filter: {stats['kept']}/{stats['total']} kept "
              f"({stats['filter_rate']*100:.0f}% filtered)")
    
    return quality_comments, stats

