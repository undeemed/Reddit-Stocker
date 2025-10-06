"""
Script 1 (LLM Version): Track hot stocks using LLM-based extraction.

Usage:
    python stock_tracker_llm.py --test-mode --post-limit 20 --top-comments 10
    python stock_tracker_llm.py --timeframe week --subreddits 1-3 --post-limit 100
    python stock_tracker_llm.py --subreddits 1,3,5 --post-limit 50
"""
import argparse
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from config import STOCK_SUBREDDITS
from database import init_database, save_stock_mentions
from reddit_client_llm import get_subreddit_tickers_llm
from llm_extractor import get_available_models
from llm_manager import MultiModelManager
from setup_checker import check_setup, prompt_openrouter_setup


def parse_subreddit_selection(selection_str: str, subreddit_list: list) -> list:
    """
    Parse subreddit selection string.
    
    Supports:
    - Single: "3" -> [subreddit_list[2]]
    - Multiple: "1,3,5" -> [subreddit_list[0], subreddit_list[2], subreddit_list[4]]
    - Ranges: "1-5" -> first 5 subreddits
    - Mixed: "1,3-5,8" -> [1st, 3rd-5th, 8th]
    
    Args:
        selection_str: Selection string (e.g., "1-3", "1,5,8", "2-4")
        subreddit_list: List of all subreddits
        
    Returns:
        List of selected subreddits
    """
    selected = []
    parts = selection_str.split(',')
    
    for part in parts:
        part = part.strip()
        if '-' in part:
            # Range (e.g., "1-5")
            try:
                start, end = part.split('-')
                start_idx = int(start) - 1  # Convert to 0-based
                end_idx = int(end)  # End is inclusive, so we use it directly
                
                if start_idx < 0 or end_idx > len(subreddit_list):
                    print(f"⚠️  Warning: Range {part} out of bounds (1-{len(subreddit_list)})")
                    continue
                
                selected.extend(subreddit_list[start_idx:end_idx])
            except (ValueError, IndexError):
                print(f"⚠️  Warning: Invalid range '{part}'")
                continue
        else:
            # Single number (e.g., "3")
            try:
                idx = int(part) - 1  # Convert to 0-based
                if 0 <= idx < len(subreddit_list):
                    selected.append(subreddit_list[idx])
                else:
                    print(f"⚠️  Warning: Subreddit #{part} out of bounds (1-{len(subreddit_list)})")
            except ValueError:
                print(f"⚠️  Warning: Invalid selection '{part}'")
                continue
    
    # Remove duplicates while preserving order
    seen = set()
    unique_selected = []
    for sub in selected:
        if sub not in seen:
            seen.add(sub)
            unique_selected.append(sub)
    
    return unique_selected


def show_subreddit_list():
    """Display the list of available subreddits with numbers."""
    print("\n📋 Available Subreddits:")
    print("=" * 50)
    for i, subreddit in enumerate(STOCK_SUBREDDITS, 1):
        print(f"  {i:2d}. r/{subreddit}")
    print("=" * 50)
    print("\nUsage examples:")
    print("  --subreddits 1        # Just r/wallstreetbets")
    print("  --subreddits 1-5      # First 5 subreddits")
    print("  --subreddits 1,3,5    # Subreddits #1, #3, and #5")
    print("  --subreddits 2-4,8    # Subreddits #2-4 and #8")
    print()


def process_subreddit_llm(
    subreddit_name: str,
    timeframe: str,
    model_manager,
    post_limit: int,
    comments_per_post: int,
    top_comments: int,
    batch_size: int
) -> tuple:
    """Process a subreddit with LLM extraction."""
    print(f"Processing r/{subreddit_name} with LLM...")
    ticker_counter = get_subreddit_tickers_llm(
        subreddit_name,
        timeframe,
        limit=post_limit,
        comments_per_post=comments_per_post,
        global_top_comments=top_comments,
        batch_size=batch_size,
        model_manager=model_manager
    )
    print(f"✓ Completed r/{subreddit_name}: Found {len(ticker_counter)} unique tickers")
    return (subreddit_name, ticker_counter)


def track_hot_stocks_llm(
    timeframe: str = 'day',
    model_manager = None,
    test_mode: bool = False,
    subreddit_selection: str = None,
    post_limit: int = 100,
    comments_per_post: int = 5,
    top_comments: int = 50,
    batch_size: int = 50,
    analyze_sentiment: bool = False,
    analyze_top_n: int = 3
):
    """Track hot stocks using LLM-based extraction."""
    if model_manager is None:
        model_manager = MultiModelManager()
    
    # Determine which subreddits to analyze
    if test_mode:
        subreddits = ['wallstreetbets']
    elif subreddit_selection:
        subreddits = parse_subreddit_selection(subreddit_selection, STOCK_SUBREDDITS)
        if not subreddits:
            print("❌ No valid subreddits selected. Exiting.")
            return []
    else:
        subreddits = STOCK_SUBREDDITS
    
    print(f"\n{'='*60}")
    print(f"Tracking Hot Stocks (LLM Mode) - Timeframe: {timeframe.upper()}")
    if test_mode:
        print(f"TEST MODE: Analyzing only r/{subreddits[0]}")
    elif subreddit_selection:
        print(f"Analyzing {len(subreddits)} subreddit(s): {', '.join([f'r/{s}' for s in subreddits])}")
    else:
        print(f"Analyzing all {len(subreddits)} subreddits")
    print(f"Post limit: {post_limit}, Top comments: {top_comments}, Batch size: {batch_size}")
    print(f"{'='*60}\n")
    
    print(f"Initial budget: {model_manager.get_stats()}\n")
    
    # Initialize database
    init_database()
    
    # Process subreddits in parallel
    all_tickers: Counter = Counter()
    subreddit_data = []
    
    # Use fewer workers for LLM to avoid rate limits
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_to_subreddit = {
            executor.submit(
                process_subreddit_llm,
                sub,
                timeframe,
                model_manager,
                post_limit,
                comments_per_post,
                top_comments,
                batch_size
            ): sub 
            for sub in subreddits
        }
        
        for future in as_completed(future_to_subreddit):
            try:
                subreddit_name, ticker_counter = future.result()
                all_tickers.update(ticker_counter)
                
                for ticker, count in ticker_counter.items():
                    subreddit_data.append((ticker, subreddit_name, count, timeframe))
                    
            except Exception as e:
                subreddit = future_to_subreddit[future]
                print(f"✗ Error processing r/{subreddit}: {e}")
    
    # Save to SQLite database
    if subreddit_data:
        print(f"\nSaving {len(subreddit_data)} records to database...")
        save_stock_mentions(subreddit_data)
        print("✓ Data saved to SQLite")
    
    # Save to Convex (if configured)
    try:
        import os
        if os.getenv('CONVEX_URL'):
            from convex_client import StockConvexClient
            print("\nSaving to Convex...")
            
            client = StockConvexClient()
            for ticker, count in all_tickers.most_common(10):
                # Build subreddit mentions
                subreddit_mentions = []
                for subreddit in subreddits:
                    # Find count in subreddit_data
                    for t, sub, c, tf in subreddit_data:
                        if t == ticker and sub == subreddit:
                            subreddit_mentions.append({"subreddit": sub, "count": c})
                            break
                
                # Save to Convex
                client.save_analysis(
                    ticker=ticker,
                    timeframe=timeframe,
                    total_mentions=count,
                    subreddit_mentions=subreddit_mentions,
                    average_sentiment=0.0,  # Will be updated by sentiment analyzer
                    sentiment_breakdown={"positive": 0, "neutral": 0, "negative": 0}
                )
            print("✓ Data saved to Convex")
    except Exception as e:
        # Silently ignore if Convex not configured
        if 'CONVEX_URL not found' not in str(e):
            print(f"⚠ Convex save skipped: {e}")
    
    # Display results
    print(f"\n{'='*60}")
    print(f"TOP 10 HOTTEST STOCKS (LLM-Analyzed) - {timeframe.upper()}")
    print(f"{'='*60}\n")
    
    top_stocks = all_tickers.most_common(10)
    
    if top_stocks:
        print(f"{'Rank':<6} {'Ticker':<10} {'Mentions':<10}")
        print(f"{'-'*30}")
        for rank, (ticker, count) in enumerate(top_stocks, 1):
            print(f"{rank:<6} {ticker:<10} {count:<10}")
    else:
        print("No stocks found. Check your API credentials.")
    
    print(f"\n{'='*60}\n")
    
    # Auto-analyze sentiment for top stocks if requested
    if analyze_sentiment and top_stocks:
        print(f"🔍 Auto-analyzing sentiment for top {analyze_top_n} stocks...\n")
        
        from sentiment_analyzer_llm import analyze_stock_sentiment_llm
        
        for ticker, count in top_stocks[:analyze_top_n]:
            print(f"Analyzing {ticker}...")
            try:
                analyze_stock_sentiment_llm(
                    ticker=ticker,
                    model_manager=model_manager,
                    test_mode=test_mode,
                    subreddit_selection=subreddit_selection
                )
            except Exception as e:
                print(f"⚠ Error analyzing {ticker}: {e}")
        
        print(f"\n✓ Completed sentiment analysis for top {analyze_top_n} stocks")
    
    return top_stocks


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Track hot stocks using LLM-based extraction'
    )
    parser.add_argument(
        '-t', '--timeframe',
        type=str,
        choices=['day', 'week', 'month'],
        default='day',
        help='Timeframe for tracking stocks (default: day)'
    )
    parser.add_argument(
        '-tm', '--test-mode',
        action='store_true',
        help='Test mode: analyze only r/wallstreetbets'
    )
    parser.add_argument(
        '-s', '--subreddits',
        type=str,
        help='Subreddit selection (e.g., "1", "1-5", "1,3,5", "2-4,8"). Use -ls to see options'
    )
    parser.add_argument(
        '-ls', '--list-subreddits',
        action='store_true',
        help='Show list of available subreddits with numbers'
    )
    parser.add_argument(
        '-mr', '--max-requests',
        type=int,
        default=1000,
        help='Maximum requests per day (default: 1000)'
    )
    parser.add_argument(
        '-pl', '--post-limit',
        type=int,
        default=100,
        help='Number of posts to fetch per subreddit (default: 100)'
    )
    parser.add_argument(
        '-cp', '--comments-per-post',
        type=int,
        default=5,
        help='Top N comments to fetch per post (default: 5)'
    )
    parser.add_argument(
        '-tc', '--top-comments',
        type=int,
        default=50,
        help='Top N comments to analyze globally (default: 50)'
    )
    parser.add_argument(
        '-bs', '--batch-size',
        type=int,
        default=50,
        help='Comments to batch per LLM request (default: 50, max: 100)'
    )
    parser.add_argument(
        '-lm', '--list-models',
        action='store_true',
        help='List available models'
    )
    parser.add_argument(
        '-as', '--analyze-sentiment',
        action='store_true',
        help='Auto-analyze sentiment for top stocks after tracking'
    )
    parser.add_argument(
        '-an', '--analyze-top-n',
        type=int,
        default=3,
        help='Number of top stocks to analyze (default: 3, requires -as)'
    )
    
    args = parser.parse_args()
    
    if args.list_subreddits:
        show_subreddit_list()
        return
    
    if args.list_models:
        print("\n🤖 Available Models:\n")
        for model in get_available_models():
            print(f"  • {model}")
        print("\nGet your API key at: https://openrouter.ai/keys\n")
        return
    
    # Check if setup is complete
    is_setup, message = check_setup()
    if not is_setup:
        print(message)
        exit(1)
    
    # Check for OpenRouter API key for LLM features
    if not os.getenv('OPENROUTER_API_KEY'):
        print(prompt_openrouter_setup())
        exit(1)
    
    # Validate that test-mode and subreddits aren't both specified
    if args.test_mode and args.subreddits:
        print("⚠️  Warning: --test-mode overrides --subreddits selection")
    
    try:
        model_manager = MultiModelManager(max_requests_per_day=args.max_requests)
        track_hot_stocks_llm(
            timeframe=args.timeframe,
            model_manager=model_manager,
            test_mode=args.test_mode,
            subreddit_selection=args.subreddits,
            post_limit=args.post_limit,
            comments_per_post=args.comments_per_post,
            top_comments=args.top_comments,
            batch_size=args.batch_size,
            analyze_sentiment=args.analyze_sentiment,
            analyze_top_n=args.analyze_top_n
        )
    except KeyboardInterrupt:
        print("\n\nTracking interrupted by user.")
    except Exception as e:
        print(f"\nError: {e}")
        print("\nMake sure you have:")
        print("1. Set OPENROUTER_API_KEY in .env file")
        print("2. Set Reddit API credentials in .env file")
        print("3. Installed all requirements: pip install -r requirements.txt")


if __name__ == '__main__':
    main()

