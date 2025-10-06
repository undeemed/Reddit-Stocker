"""
Script 1: Track the top 10 hottest stocks across top stock subreddits.

Usage:
    python stock_tracker.py --timeframe day
    python stock_tracker.py --timeframe week
    python stock_tracker.py --timeframe month
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from config import STOCK_SUBREDDITS
from database import init_database, save_stock_mentions
from reddit_client import get_subreddit_tickers
from setup_checker import check_setup


def process_subreddit(subreddit_name: str, timeframe: str) -> tuple:
    """
    Process a single subreddit and return ticker counts.
    
    Args:
        subreddit_name: Name of the subreddit to process
        timeframe: 'day', 'week', or 'month'
        
    Returns:
        Tuple of (subreddit_name, ticker_counter)
    """
    print(f"Processing r/{subreddit_name}...")
    ticker_counter = get_subreddit_tickers(subreddit_name, timeframe)
    print(f"✓ Completed r/{subreddit_name}: Found {len(ticker_counter)} unique tickers")
    return (subreddit_name, ticker_counter)


def track_hot_stocks(timeframe: str = 'day'):
    """
    Track hot stocks across all subreddits in parallel.
    
    Args:
        timeframe: 'day', 'week', or 'month'
    """
    print(f"\n{'='*60}")
    print(f"Tracking Hot Stocks - Timeframe: {timeframe.upper()}")
    print(f"{'='*60}\n")
    
    # Initialize database
    init_database()
    
    # Process all subreddits in parallel
    all_tickers: Counter = Counter()
    subreddit_data = []
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        # Submit all tasks
        future_to_subreddit = {
            executor.submit(process_subreddit, sub, timeframe): sub 
            for sub in STOCK_SUBREDDITS
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_subreddit):
            try:
                subreddit_name, ticker_counter = future.result()
                
                # Aggregate global ticker counts
                all_tickers.update(ticker_counter)
                
                # Prepare data for database storage
                for ticker, count in ticker_counter.items():
                    subreddit_data.append((ticker, subreddit_name, count, timeframe))
                    
            except Exception as e:
                subreddit = future_to_subreddit[future]
                print(f"✗ Error processing r/{subreddit}: {e}")
    
    # Save to database
    if subreddit_data:
        print(f"\nSaving {len(subreddit_data)} records to database...")
        save_stock_mentions(subreddit_data)
        print("✓ Data saved successfully")
    
    # Display top 10 hottest stocks
    print(f"\n{'='*60}")
    print(f"TOP 10 HOTTEST STOCKS - {timeframe.upper()}")
    print(f"{'='*60}\n")
    
    top_stocks = all_tickers.most_common(10)
    
    if top_stocks:
        print(f"{'Rank':<6} {'Ticker':<10} {'Mentions':<10}")
        print(f"{'-'*30}")
        for rank, (ticker, count) in enumerate(top_stocks, 1):
            print(f"{rank:<6} {ticker:<10} {count:<10}")
    else:
        print("No stocks found. Check your Reddit API credentials.")
    
    print(f"\n{'='*60}\n")
    
    return top_stocks


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Track the hottest stocks on Reddit'
    )
    parser.add_argument(
        '--timeframe',
        type=str,
        choices=['day', 'week', 'month'],
        default='day',
        help='Timeframe for tracking stocks (default: day)'
    )
    
    args = parser.parse_args()
    
    # Check if setup is complete
    is_setup, message = check_setup()
    if not is_setup:
        print(message)
        exit(1)
    
    try:
        track_hot_stocks(args.timeframe)
    except KeyboardInterrupt:
        print("\n\nTracking interrupted by user.")
    except Exception as e:
        print(f"\nError: {e}")
        print("\nMake sure you have:")
        print("1. Created a .env file with Reddit API credentials")
        print("2. Installed all requirements: pip install -r requirements.txt")


if __name__ == '__main__':
    main()

