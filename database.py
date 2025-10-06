"""Database operations for storing stock mentions and sentiment data."""
import sqlite3
from datetime import datetime
from typing import List, Tuple, Optional
from config import DATABASE_PATH


def init_database():
    """Initialize the SQLite database with required tables."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Table for stock mentions
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_mentions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            subreddit TEXT NOT NULL,
            mention_count INTEGER NOT NULL,
            timeframe TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ticker, subreddit, timeframe, timestamp)
        )
    ''')
    
    # Table for sentiment analysis
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_sentiment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            subreddit TEXT NOT NULL,
            post_id TEXT NOT NULL,
            sentiment_score REAL NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create indexes for faster queries
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_ticker_timeframe 
        ON stock_mentions(ticker, timeframe)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_sentiment_ticker 
        ON stock_sentiment(ticker)
    ''')
    
    conn.commit()
    conn.close()


def save_stock_mentions(mentions: List[Tuple[str, str, int, str]]):
    """
    Save stock mentions to database.
    
    Args:
        mentions: List of tuples (ticker, subreddit, count, timeframe)
    """
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    for ticker, subreddit, count, timeframe in mentions:
        cursor.execute('''
            INSERT OR REPLACE INTO stock_mentions 
            (ticker, subreddit, mention_count, timeframe, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (ticker, subreddit, count, timeframe, timestamp))
    
    conn.commit()
    conn.close()


def save_sentiment(ticker: str, subreddit: str, post_id: str, sentiment_score: float):
    """Save sentiment analysis result to database."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO stock_sentiment (ticker, subreddit, post_id, sentiment_score)
        VALUES (?, ?, ?, ?)
    ''', (ticker, subreddit, post_id, sentiment_score))
    
    conn.commit()
    conn.close()


def get_top_stocks(timeframe: str, limit: int = 10) -> List[Tuple[str, int]]:
    """
    Get top stocks by mention count for a given timeframe.
    
    Args:
        timeframe: 'day', 'week', or 'month'
        limit: Number of top stocks to return
        
    Returns:
        List of tuples (ticker, total_mentions)
    """
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT ticker, SUM(mention_count) as total_mentions
        FROM stock_mentions
        WHERE timeframe = ?
        AND date(timestamp) = date('now')
        GROUP BY ticker
        ORDER BY total_mentions DESC
        LIMIT ?
    ''', (timeframe, limit))
    
    results = cursor.fetchall()
    conn.close()
    
    return results


def get_stock_sentiment(ticker: str) -> Optional[dict]:
    """
    Get sentiment statistics for a specific stock ticker.
    
    Args:
        ticker: Stock ticker symbol
        
    Returns:
        Dictionary with sentiment statistics or None if no data found
    """
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            AVG(sentiment_score) as avg_sentiment,
            COUNT(*) as total_posts,
            SUM(CASE WHEN sentiment_score > 0.05 THEN 1 ELSE 0 END) as positive,
            SUM(CASE WHEN sentiment_score < -0.05 THEN 1 ELSE 0 END) as negative,
            SUM(CASE WHEN sentiment_score BETWEEN -0.05 AND 0.05 THEN 1 ELSE 0 END) as neutral
        FROM stock_sentiment
        WHERE ticker = ?
        AND date(timestamp) = date('now')
    ''', (ticker,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result[1] == 0:  # No data found
        return None
    
    return {
        'avg_sentiment': result[0],
        'total_posts': result[1],
        'positive': result[2],
        'negative': result[3],
        'neutral': result[4]
    }

