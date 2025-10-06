"""
Ticker validation using the US-Stock-Symbols GitHub repository.
Updated nightly by GitHub Actions with real NASDAQ, NYSE, and AMEX symbols.
"""
import requests
import json
import os
from datetime import datetime, timedelta
from typing import Set

# GitHub raw URLs for ticker lists
TICKER_SOURCES = {
    'nasdaq': 'https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/nasdaq/nasdaq_tickers.txt',
    'nyse': 'https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/nyse/nyse_tickers.txt',
    'amex': 'https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/amex/amex_tickers.txt'
}

CACHE_FILE = 'valid_tickers_cache.json'
CACHE_DURATION_HOURS = 24  # Refresh once per day


def fetch_valid_tickers() -> Set[str]:
    """
    Fetch valid US stock tickers from GitHub repository.
    Uses local cache if available and less than 24 hours old.
    
    Returns:
        Set of valid ticker symbols
    """
    # Check cache first
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                cache_data = json.load(f)
                cache_time = datetime.fromisoformat(cache_data['timestamp'])
                
                # Use cache if less than 24 hours old
                if datetime.now() - cache_time < timedelta(hours=CACHE_DURATION_HOURS):
                    print(f"✓ Using cached ticker list ({len(cache_data['tickers'])} tickers)")
                    return set(cache_data['tickers'])
        except Exception as e:
            print(f"Warning: Cache read failed: {e}")
    
    # Fetch fresh data
    print("Fetching latest ticker list from GitHub...")
    valid_tickers = set()
    
    for exchange, url in TICKER_SOURCES.items():
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            # Parse newline-separated tickers
            tickers = [line.strip() for line in response.text.strip().split('\n') if line.strip()]
            valid_tickers.update(tickers)
            print(f"✓ Fetched {len(tickers)} tickers from {exchange.upper()}")
            
        except Exception as e:
            print(f"⚠ Warning: Failed to fetch {exchange.upper()} tickers: {e}")
    
    if valid_tickers:
        # Save to cache
        try:
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'tickers': list(valid_tickers)
            }
            with open(CACHE_FILE, 'w') as f:
                json.dump(cache_data, f)
            print(f"✓ Cached {len(valid_tickers)} valid tickers")
        except Exception as e:
            print(f"Warning: Cache write failed: {e}")
    else:
        print("⚠ Warning: No tickers fetched. Check your internet connection.")
    
    return valid_tickers


def is_valid_ticker(ticker: str, valid_tickers: Set[str]) -> bool:
    """
    Check if a ticker is valid.
    
    Args:
        ticker: Ticker symbol to validate
        valid_tickers: Set of valid ticker symbols
        
    Returns:
        True if ticker is valid
    """
    return ticker in valid_tickers


def force_refresh_tickers():
    """Force refresh the ticker cache."""
    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)
    return fetch_valid_tickers()

