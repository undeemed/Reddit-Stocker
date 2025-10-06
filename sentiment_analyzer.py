"""
Script 2: Analyze Reddit sentiment for a specific stock ticker.

Usage:
    python sentiment_analyzer.py AAPL
    python sentiment_analyzer.py TSLA
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from config import STOCK_SUBREDDITS
from database import init_database, save_sentiment
from reddit_client import get_ticker_posts
from setup_checker import check_setup


def analyze_sentiment(text: str, analyzer: SentimentIntensityAnalyzer) -> float:
    """
    Analyze sentiment of text using VADER.
    
    Args:
        text: Text to analyze
        analyzer: VADER sentiment analyzer instance
        
    Returns:
        Compound sentiment score (-1 to 1)
    """
    scores = analyzer.polarity_scores(text)
    return scores['compound']


def process_subreddit_sentiment(subreddit_name: str, ticker: str, analyzer: SentimentIntensityAnalyzer) -> list:
    """
    Process sentiment for a ticker in a single subreddit.
    
    Args:
        subreddit_name: Name of the subreddit
        ticker: Stock ticker to analyze
        analyzer: VADER sentiment analyzer instance
        
    Returns:
        List of sentiment scores
    """
    print(f"Analyzing r/{subreddit_name}...")
    
    posts = get_ticker_posts(subreddit_name, ticker)
    sentiments = []
    
    for post in posts:
        sentiment_score = analyze_sentiment(post['text'], analyzer)
        sentiments.append({
            'subreddit': subreddit_name,
            'post_id': post['id'],
            'sentiment': sentiment_score,
            'title': post['title'],
            'score': post['score']
        })
        
        # Save to database
        save_sentiment(ticker, subreddit_name, post['id'], sentiment_score)
    
    print(f"✓ r/{subreddit_name}: Analyzed {len(sentiments)} posts")
    
    return sentiments


def analyze_stock_sentiment(ticker: str):
    """
    Analyze sentiment for a stock ticker across all subreddits.
    
    Args:
        ticker: Stock ticker symbol
    """
    ticker = ticker.upper()
    
    print(f"\n{'='*60}")
    print(f"Analyzing Sentiment for ${ticker}")
    print(f"{'='*60}\n")
    
    # Initialize database and sentiment analyzer
    init_database()
    analyzer = SentimentIntensityAnalyzer()
    
    # Process all subreddits in parallel
    all_sentiments = []
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        # Submit all tasks
        future_to_subreddit = {
            executor.submit(process_subreddit_sentiment, sub, ticker, analyzer): sub
            for sub in STOCK_SUBREDDITS
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_subreddit):
            try:
                sentiments = future.result()
                all_sentiments.extend(sentiments)
            except Exception as e:
                subreddit = future_to_subreddit[future]
                print(f"✗ Error processing r/{subreddit}: {e}")
    
    # Calculate overall sentiment
    if not all_sentiments:
        print(f"\n⚠ No recent mentions found for ${ticker}")
        print("Try a different ticker or check back later.\n")
        return
    
    # Aggregate sentiment statistics
    sentiment_scores = [s['sentiment'] for s in all_sentiments]
    avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)
    
    positive_count = sum(1 for s in sentiment_scores if s > 0.05)
    negative_count = sum(1 for s in sentiment_scores if s < -0.05)
    neutral_count = len(sentiment_scores) - positive_count - negative_count
    
    # Display results
    print(f"\n{'='*60}")
    print(f"SENTIMENT ANALYSIS RESULTS - ${ticker}")
    print(f"{'='*60}\n")
    
    print(f"Total Posts Analyzed: {len(all_sentiments)}")
    print(f"\nOverall Sentiment Score: {avg_sentiment:.3f}")
    
    # Sentiment interpretation
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
    
    # Top mentioned subreddits
    print(f"\n{'='*60}")
    print("TOP SUBREDDITS BY MENTION COUNT")
    print(f"{'='*60}\n")
    
    subreddit_counts: dict[str, int] = {}
    for s in all_sentiments:
        sub = s['subreddit']
        subreddit_counts[sub] = subreddit_counts.get(sub, 0) + 1
    
    sorted_subreddits = sorted(subreddit_counts.items(), key=lambda x: x[1], reverse=True)
    
    print(f"{'Subreddit':<25} {'Mentions':<10}")
    print(f"{'-'*35}")
    for sub, count in sorted_subreddits[:5]:
        print(f"r/{sub:<24} {count:<10}")
    
    # Show sample posts
    print(f"\n{'='*60}")
    print("SAMPLE POSTS (Top by Score)")
    print(f"{'='*60}\n")
    
    # Sort by Reddit score and show top 3
    top_posts = sorted(all_sentiments, key=lambda x: x['score'], reverse=True)[:3]
    
    for i, post in enumerate(top_posts, 1):
        sentiment_emoji = "📈" if post['sentiment'] > 0.05 else "📉" if post['sentiment'] < -0.05 else "➡️"
        print(f"{i}. {sentiment_emoji} [{post['subreddit']}] Score: {post['sentiment']:.3f}")
        print(f"   {post['title'][:100]}...")
        print()
    
    print(f"{'='*60}\n")


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Analyze Reddit sentiment for a stock ticker'
    )
    parser.add_argument(
        'ticker',
        type=str,
        help='Stock ticker symbol (e.g., AAPL, TSLA)'
    )
    
    args = parser.parse_args()
    
    # Check if setup is complete
    is_setup, message = check_setup()
    if not is_setup:
        print(message)
        exit(1)
    
    try:
        analyze_stock_sentiment(args.ticker)
    except KeyboardInterrupt:
        print("\n\nAnalysis interrupted by user.")
    except Exception as e:
        print(f"\nError: {e}")
        print("\nMake sure you have:")
        print("1. Created a .env file with Reddit API credentials")
        print("2. Installed all requirements: pip install -r requirements.txt")


if __name__ == '__main__':
    main()

