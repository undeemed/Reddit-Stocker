"""Configuration settings for StockReddit."""
import os
from dotenv import load_dotenv

load_dotenv()

# Reddit API credentials
REDDIT_CLIENT_ID = os.getenv('REDDIT_CLIENT_ID')
REDDIT_CLIENT_SECRET = os.getenv('REDDIT_CLIENT_SECRET')
REDDIT_USER_AGENT = os.getenv('REDDIT_USER_AGENT', 'StockReddit/1.0')

# Top stock subreddits to monitor
STOCK_SUBREDDITS = [
    'wallstreetbets',
    'stocks',
    'investing',
    'StockMarket',
    'options',
    'pennystocks',
    'Daytrading',
    'swingtrading',
    'RobinHood',
    'SecurityAnalysis'
]

# Database settings
DATABASE_PATH = 'stocks.db'

# Stock ticker pattern (common US stock tickers: 1-5 uppercase letters)
TICKER_PATTERN = r'\b[A-Z]{1,5}\b'

# Common words to filter out (not stock tickers)
COMMON_WORDS = {
    'THE', 'AND', 'FOR', 'ARE', 'BUT', 'NOT', 'YOU', 'ALL', 'CAN', 'HER',
    'ONE', 'OUR', 'OUT', 'DAY', 'GET', 'HAS', 'HIM', 'HIS', 'HOW', 'WAS',
    'ITS', 'MAY', 'NEW', 'NOW', 'OLD', 'SEE', 'TWO', 'WAY', 'WHO', 'BOY',
    'DID', 'LET', 'PUT', 'SAY', 'SHE', 'TOO', 'USE', 'WON', 'YES', 'YET',
    'YOLO', 'LMAO', 'IMO', 'TBH', 'IDK', 'AMA', 'ELI', 'TIL', 'PSA', 'EDIT',
    'TLDR', 'NSFW', 'CEO', 'CFO', 'IPO', 'ETF', 'USD', 'USA', 'SEC', 'FDA',
    'ATH', 'ATL', 'EOD', 'AH', 'PM', 'DD', 'TA', 'FA', 'WSB', 'OP', 'LOL',
    'WTF', 'FYI', 'ASAP', 'BTW',
    # Single-letter tickers that are commonly used as words
    'I', 'A'
}

