"""
Script 2 (LLM Version): Analyze sentiment with LLM context understanding.

Usage:
    python sentiment_analyzer_llm.py AAPL --test-mode
    python sentiment_analyzer_llm.py TSLA --subreddits 1-3
    python sentiment_analyzer_llm.py NVDA --subreddits 1,3,5
"""
import argparse
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from config import STOCK_SUBREDDITS
from database import init_database, save_sentiment
from reddit_client_llm import get_ticker_sentiment_llm
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


def analyze_sentiment_with_context(text: str, llm_context: str, analyzer: SentimentIntensityAnalyzer) -> dict:
    """
    Analyze sentiment considering LLM-extracted context.
    
    Args:
        text: Original text
        llm_context: LLM's interpretation of the discussion
        analyzer: VADER sentiment analyzer
        
    Returns:
        Dictionary with sentiment scores and context
    """
    # Get VADER sentiment
    vader_scores = analyzer.polarity_scores(text)
    
    # Use LLM context for better understanding
    if llm_context:
        context_scores = analyzer.polarity_scores(llm_context)
        # Weighted average: 60% original, 40% LLM context
        compound = (vader_scores['compound'] * 0.6) + (context_scores['compound'] * 0.4)
    else:
        compound = vader_scores['compound']
    
    return {
        'compound': compound,
        'vader_scores': vader_scores,
        'llm_context': llm_context
    }


def process_subreddit_sentiment_llm(
    subreddit_name: str,
    ticker: str,
    analyzer: SentimentIntensityAnalyzer,
    model_manager
) -> list:
    """Process sentiment for a ticker in a subreddit using LLM."""
    print(f"Analyzing r/{subreddit_name} with LLM...")
    
    posts = get_ticker_sentiment_llm(subreddit_name, ticker, model_manager=model_manager)
    sentiments = []
    
    for post in posts:
        sentiment_data = analyze_sentiment_with_context(
            post['text'],
            post.get('llm_context', ''),
            analyzer
        )
        
        sentiments.append({
            'subreddit': subreddit_name,
            'post_id': post['id'],
            'sentiment': sentiment_data['compound'],
            'title': post['title'],
            'score': post['score'],
            'llm_context': sentiment_data['llm_context']
        })
        
        # Save to database
        save_sentiment(ticker, subreddit_name, post['id'], sentiment_data['compound'])
    
    print(f"✓ r/{subreddit_name}: Analyzed {len(sentiments)} posts with context")
    
    return sentiments


def analyze_stock_sentiment_llm(
    ticker: str,
    model_manager = None,
    test_mode: bool = False,
    subreddit_selection: str = None
):
    """Analyze sentiment with LLM-enhanced context."""
    ticker = ticker.upper()
    
    if model_manager is None:
        model_manager = MultiModelManager()
    
    # Determine which subreddits to analyze
    if test_mode:
        subreddits = ['wallstreetbets']
    elif subreddit_selection:
        subreddits = parse_subreddit_selection(subreddit_selection, STOCK_SUBREDDITS)
        if not subreddits:
            print("❌ No valid subreddits selected. Exiting.")
            return
    else:
        subreddits = STOCK_SUBREDDITS
    
    print(f"\n{'='*60}")
    print(f"Analyzing Sentiment for ${ticker} (LLM Mode)")
    if test_mode:
        print(f"TEST MODE: Analyzing only r/{subreddits[0]}")
    elif subreddit_selection:
        print(f"Analyzing {len(subreddits)} subreddit(s): {', '.join([f'r/{s}' for s in subreddits])}")
    else:
        print(f"Analyzing all {len(subreddits)} subreddits")
    print(f"Initial budget: {model_manager.get_stats()}")
    print(f"{'='*60}\n")
    
    # Initialize
    init_database()
    analyzer = SentimentIntensityAnalyzer()
    
    # Process subreddits in parallel
    all_sentiments = []
    
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_to_subreddit = {
            executor.submit(process_subreddit_sentiment_llm, sub, ticker, analyzer, model_manager): sub
            for sub in subreddits
        }
        
        for future in as_completed(future_to_subreddit):
            try:
                sentiments = future.result()
                all_sentiments.extend(sentiments)
            except Exception as e:
                subreddit = future_to_subreddit[future]
                print(f"✗ Error processing r/{subreddit}: {e}")
    
    # Display results
    if not all_sentiments:
        print(f"\n⚠ No recent mentions found for ${ticker}\n")
        return
    
    sentiment_scores = [s['sentiment'] for s in all_sentiments]
    avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)
    
    positive_count = sum(1 for s in sentiment_scores if s > 0.05)
    negative_count = sum(1 for s in sentiment_scores if s < -0.05)
    neutral_count = len(sentiment_scores) - positive_count - negative_count
    
    print(f"\n{'='*60}")
    print(f"SENTIMENT ANALYSIS RESULTS - ${ticker}")
    print(f"{'='*60}\n")
    
    print(f"Total Posts Analyzed: {len(all_sentiments)}")
    print(f"\nOverall Sentiment Score: {avg_sentiment:.3f}")
    
    if avg_sentiment >= 0.05:
        sentiment_label = "POSITIVE 📈"
    elif avg_sentiment <= -0.05:
        sentiment_label = "NEGATIVE 📉"
    else:
        sentiment_label = "NEUTRAL ➡️"
    
    print(f"Overall Sentiment: {sentiment_label}\n")
    
    # Sentiment breakdown
    print(f"{'Sentiment':<15} {'Count':<10} {'Percentage':<10}")
    print(f"{'-'*35}")
    print(f"{'Positive':<15} {positive_count:<10} {(positive_count/len(all_sentiments)*100):.1f}%")
    print(f"{'Neutral':<15} {neutral_count:<10} {(neutral_count/len(all_sentiments)*100):.1f}%")
    print(f"{'Negative':<15} {negative_count:<10} {(negative_count/len(all_sentiments)*100):.1f}%")
    
    # Show LLM context insights
    print(f"\n{'='*60}")
    print("LLM CONTEXT INSIGHTS (Top Posts)")
    print(f"{'='*60}\n")
    
    top_posts = sorted(all_sentiments, key=lambda x: x['score'], reverse=True)[:5]
    
    for i, post in enumerate(top_posts, 1):
        sentiment_emoji = "📈" if post['sentiment'] > 0.05 else "📉" if post['sentiment'] < -0.05 else "➡️"
        print(f"{i}. {sentiment_emoji} [{post['subreddit']}] Sentiment: {post['sentiment']:.3f}")
        print(f"   Title: {post['title'][:80]}...")
        if post.get('llm_context'):
            print(f"   Context: {post['llm_context'][:100]}...")
        print()
    
    print(f"{'='*60}\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Analyze stock sentiment with LLM context understanding'
    )
    parser.add_argument(
        'ticker',
        type=str,
        help='Stock ticker symbol (e.g., AAPL, TSLA)'
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
        '-lm', '--list-models',
        action='store_true',
        help='List available models'
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
        analyze_stock_sentiment_llm(
            args.ticker,
            model_manager=model_manager,
            test_mode=args.test_mode,
            subreddit_selection=args.subreddits
        )
    except KeyboardInterrupt:
        print("\n\nAnalysis interrupted by user.")
    except Exception as e:
        print(f"\nError: {e}")
        print("\nMake sure you have:")
        print("1. Set OPENROUTER_API_KEY in .env file")
        print("2. Set Reddit API credentials in .env file")
        print("3. Installed all requirements: pip install -r requirements.txt")


if __name__ == '__main__':
    main()

