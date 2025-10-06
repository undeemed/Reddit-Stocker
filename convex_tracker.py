"""
Stock Tracker with Convex Integration

Extends the stock tracking functionality to store results in Convex database
for real-time access, historical tracking, and AI re-evaluation.
"""
import argparse
import os
from collections import Counter
from typing import List, Dict, Any
from convex_client import StockConvexClient, test_convex_connection
from stock_tracker_llm import track_hot_stocks_llm
from sentiment_analyzer_llm import analyze_stock_sentiment_llm
from llm_manager import MultiModelManager
from setup_checker import check_setup, prompt_openrouter_setup


def save_tracking_results_to_convex(
    top_stocks: List[tuple],
    timeframe: str,
    subreddit_data: Dict[str, Counter],
    model_manager: MultiModelManager = None
) -> None:
    """
    Save stock tracking results to Convex with AI-generated summaries.
    
    Args:
        top_stocks: List of (ticker, count) tuples
        timeframe: Analysis timeframe
        subreddit_data: Dictionary of subreddit -> Counter(ticker: count)
        model_manager: Optional AI model manager for generating summaries
    """
    client = StockConvexClient()
    
    print(f"\n{'='*60}")
    print("Saving Results to Convex Database")
    print(f"{'='*60}\n")
    
    for ticker, total_count in top_stocks:
        print(f"Saving {ticker}...")
        
        # Build subreddit mentions list
        subreddit_mentions = []
        for subreddit, counter in subreddit_data.items():
            if ticker in counter:
                subreddit_mentions.append({
                    "subreddit": subreddit,
                    "count": counter[ticker]
                })
        
        # Generate AI summary if model manager provided
        ai_summary = None
        if model_manager:
            try:
                summary_prompt = f"Summarize the Reddit sentiment for ${ticker} stock in 1-2 sentences."
                ai_summary, _ = model_manager.make_request_with_retry(
                    [{"role": "user", "content": summary_prompt}]
                )
            except Exception as e:
                print(f"  ⚠ Could not generate AI summary: {e}")
        
        # Save to Convex (sentiment data will be added by sentiment analyzer)
        result = client.save_analysis(
            ticker=ticker,
            timeframe=timeframe,
            total_mentions=total_count,
            subreddit_mentions=subreddit_mentions,
            average_sentiment=0.0,  # Placeholder, updated by sentiment analysis
            sentiment_breakdown={"positive": 0, "neutral": 0, "negative": 0},
            ai_summary=ai_summary
        )
        
        status = "updated" if result.get("updated") else "created"
        print(f"  ✓ {ticker} {status}")
    
    print(f"\n✓ Saved {len(top_stocks)} stocks to Convex")
    print(f"{'='*60}\n")


def save_sentiment_to_convex(
    ticker: str,
    timeframe: str,
    all_sentiments: List[Dict[str, Any]],
    total_mentions: int = None
) -> None:
    """
    Save sentiment analysis results to Convex.
    
    Args:
        ticker: Stock ticker symbol
        timeframe: Analysis timeframe
        all_sentiments: List of sentiment dictionaries from analysis
        total_mentions: Optional total mentions (from tracking)
    """
    client = StockConvexClient()
    
    if not all_sentiments:
        print("⚠ No sentiment data to save")
        return
    
    # Calculate sentiment statistics
    sentiment_scores = [s['sentiment'] for s in all_sentiments]
    avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)
    
    positive_count = sum(1 for s in sentiment_scores if s > 0.05)
    negative_count = sum(1 for s in sentiment_scores if s < -0.05)
    neutral_count = len(sentiment_scores) - positive_count - negative_count
    
    # Build subreddit mentions
    subreddit_counter = Counter()
    for s in all_sentiments:
        subreddit_counter[s['subreddit']] += 1
    
    subreddit_mentions = [
        {"subreddit": sub, "count": count}
        for sub, count in subreddit_counter.items()
    ]
    
    # Compile AI context from top posts
    top_posts = sorted(all_sentiments, key=lambda x: x['score'], reverse=True)[:5]
    ai_context_parts = []
    for post in top_posts:
        if post.get('llm_context'):
            ai_context_parts.append(f"[{post['subreddit']}] {post['llm_context']}")
    
    ai_context = " | ".join(ai_context_parts) if ai_context_parts else None
    
    # Prepare raw posts for re-evaluation
    raw_posts = [
        {
            "postId": s['post_id'],
            "subreddit": s['subreddit'],
            "title": s['title'],
            "text": s.get('text', ''),
            "score": s['score'],
            "sentiment": s['sentiment'],
            "llmContext": s.get('llm_context'),
        }
        for s in all_sentiments
    ]
    
    # Save to Convex
    result = client.save_analysis(
        ticker=ticker,
        timeframe=timeframe,
        total_mentions=total_mentions or len(all_sentiments),
        subreddit_mentions=subreddit_mentions,
        average_sentiment=avg_sentiment,
        sentiment_breakdown={
            "positive": positive_count,
            "neutral": neutral_count,
            "negative": negative_count,
        },
        ai_context=ai_context,
        raw_posts=raw_posts
    )
    
    status = "updated" if result.get("updated") else "created"
    print(f"\n✓ Sentiment data {status} in Convex for ${ticker}")


def revaluate_stock(
    ticker: str,
    model_manager: MultiModelManager = None
) -> None:
    """
    Re-evaluate a stock using AI with stored raw data.
    
    Args:
        ticker: Stock ticker symbol to re-evaluate
        model_manager: AI model manager
    """
    client = StockConvexClient()
    
    print(f"\n{'='*60}")
    print(f"Re-evaluating ${ticker} with AI")
    print(f"{'='*60}\n")
    
    # Get existing analysis
    analysis = client.get_analysis(ticker)
    if not analysis:
        print(f"❌ No analysis found for ${ticker}")
        print("   Run analysis first: python run.py analyze-ai {ticker}")
        return
    
    # Check for raw posts
    raw_posts = analysis.get('rawPosts', [])
    if not raw_posts:
        print(f"⚠ No raw post data available for ${ticker}")
        print("   Re-run analysis to capture raw data")
        return
    
    if model_manager is None:
        model_manager = MultiModelManager()
    
    print(f"Found {len(raw_posts)} posts to re-analyze...")
    print(f"Current sentiment: {analysis['averageSentiment']:.3f}")
    print(f"Current version: {analysis.get('analysisVersion', 1)}\n")
    
    # Re-calculate statistics (sentiment scores already stored)
    try:
        updated_sentiments = [p['sentiment'] for p in raw_posts]
        
        avg_sentiment = sum(updated_sentiments) / len(updated_sentiments)
        positive = sum(1 for s in updated_sentiments if s > 0.05)
        negative = sum(1 for s in updated_sentiments if s < -0.05)
        neutral = len(updated_sentiments) - positive - negative
        
        # Generate new AI summary with fresh analysis
        # Compile context from posts for summary
        post_summaries = []
        for post in raw_posts[:10]:  # Top 10 posts
            context = post.get('llmContext', post.get('title', ''))
            if context:
                post_summaries.append(context[:200])
        
        summary_prompt = (
            f"Based on these Reddit discussions about ${ticker}, "
            f"provide a 2-3 sentence summary of the overall sentiment:\n\n"
            + "\n".join(post_summaries)
        )
        
        ai_summary, _ = model_manager.make_request_with_retry(
            [{"role": "user", "content": summary_prompt}]
        )
        
        # Update in Convex
        result = client.save_analysis(
            ticker=ticker,
            timeframe=analysis['timeframe'],
            total_mentions=analysis['totalMentions'],
            subreddit_mentions=analysis['subredditMentions'],
            average_sentiment=avg_sentiment,
            sentiment_breakdown={
                "positive": positive,
                "neutral": neutral,
                "negative": negative,
            },
            ai_summary=ai_summary,
            raw_posts=raw_posts
        )
        
        print(f"\n{'='*60}")
        print("Re-evaluation Complete")
        print(f"{'='*60}")
        print(f"New sentiment: {avg_sentiment:.3f}")
        print(f"Change: {avg_sentiment - analysis['averageSentiment']:+.3f}")
        print(f"New version: {analysis.get('analysisVersion', 1) + 1}")
        print(f"\nAI Summary:\n{ai_summary}")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"\n❌ Re-evaluation failed: {e}")


def list_convex_analyses(timeframe: str = None, limit: int = 20, sort_by: str = 'sentiment') -> None:
    """
    List all analyses stored in Convex.
    
    Args:
        timeframe: Optional timeframe filter
        limit: Maximum number of results
        sort_by: Sort by 'sentiment' or 'mentions' (default: sentiment)
    """
    client = StockConvexClient()
    
    analyses = client.list_analyses(timeframe=timeframe, limit=limit)
    
    if not analyses:
        print("\n📭 No analyses found in Convex")
        print("   Run tracking first: python run.py track-ai\n")
        return
    
    # Sort analyses
    if sort_by == 'mentions':
        analyses = sorted(analyses, key=lambda x: x['totalMentions'], reverse=True)
        sort_label = "by Mentions"
    else:  # sentiment
        analyses = sorted(analyses, key=lambda x: abs(x['averageSentiment']), reverse=True)
        sort_label = "by Sentiment Strength"
    
    print(f"\n{'='*60}")
    print(f"Stock Analyses in Convex ({len(analyses)} found) - Sorted {sort_label}")
    print(f"{'='*60}\n")
    print(f"{'Ticker':<8} {'Mentions':<10} {'Sentiment':<12} {'Version':<8} {'Updated'}")
    print(f"{'-'*60}")
    
    for analysis in analyses:
        ticker = analysis['ticker']
        mentions = analysis['totalMentions']
        # Prefer weighted sentiment score if available, fallback to average
        sentiment = analysis.get('sentimentScore', analysis['averageSentiment'])
        version = analysis.get('analysisVersion', 1)
        
        import datetime
        updated = datetime.datetime.fromtimestamp(
            analysis['lastUpdated'] / 1000
        ).strftime('%Y-%m-%d %H:%M')
        
        sentiment_emoji = "📈" if sentiment > 0.05 else "📉" if sentiment < -0.05 else "➡️"
        
        print(f"{ticker:<8} {mentions:<10} {sentiment_emoji} {sentiment:<10.3f} v{version:<6} {updated}")
    
    print(f"{'='*60}\n")


def show_convex_analysis(ticker: str, timeframe: str = None) -> None:
    """Display detailed analysis for a ticker from Convex."""
    client = StockConvexClient()
    
    analysis = client.get_analysis(ticker, timeframe)
    
    if not analysis:
        print(f"\n❌ No analysis found for ${ticker}")
        return
    
    import datetime
    updated = datetime.datetime.fromtimestamp(
        analysis['lastUpdated'] / 1000
    ).strftime('%Y-%m-%d %H:%M:%S')
    
    print(f"\n{'='*60}")
    print(f"Analysis for ${ticker}")
    print(f"{'='*60}")
    print(f"Timeframe: {analysis['timeframe']}")
    print(f"Total Mentions: {analysis['totalMentions']}")
    print(f"Average Sentiment: {analysis['averageSentiment']:.3f}")
    print(f"Version: {analysis.get('analysisVersion', 1)}")
    print(f"Last Updated: {updated}")
    
    print(f"\nSentiment Breakdown:")
    breakdown = analysis['sentimentBreakdown']
    total = sum(breakdown.values())
    if total > 0:
        print(f"  Positive: {breakdown['positive']} ({breakdown['positive']/total*100:.1f}%)")
        print(f"  Neutral:  {breakdown['neutral']} ({breakdown['neutral']/total*100:.1f}%)")
        print(f"  Negative: {breakdown['negative']} ({breakdown['negative']/total*100:.1f}%)")
    
    print(f"\nSubreddit Mentions:")
    for sm in analysis['subredditMentions']:
        print(f"  r/{sm['subreddit']}: {sm['count']}")
    
    if analysis.get('aiSummary'):
        print(f"\nAI Summary:")
        print(f"  {analysis['aiSummary']}")
    
    if analysis.get('aiContext'):
        print(f"\nAI Context:")
        print(f"  {analysis['aiContext'][:300]}...")
    
    print(f"{'='*60}\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Stock tracking with Convex database integration'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Test connection
    subparsers.add_parser('test', help='Test Convex connection')
    
    # List analyses
    list_parser = subparsers.add_parser('list', help='List all analyses')
    list_parser.add_argument('-t', '--timeframe', help='Filter by timeframe')
    list_parser.add_argument('-l', '--limit', type=int, default=20, help='Result limit')
    list_parser.add_argument('-m', '--sort-mentions', action='store_true', help='Sort by mentions')
    list_parser.add_argument('-s', '--sort-sentiment', action='store_true', help='Sort by sentiment (default)')
    
    # Show analysis
    show_parser = subparsers.add_parser('show', help='Show detailed analysis')
    show_parser.add_argument('ticker', help='Stock ticker symbol')
    show_parser.add_argument('-t', '--timeframe', help='Filter by timeframe')
    
    # Re-evaluate
    reeval_parser = subparsers.add_parser('reeval', help='Re-evaluate with AI')
    reeval_parser.add_argument('ticker', help='Stock ticker symbol')
    reeval_parser.add_argument('-mr', '--max-requests', type=int, default=1000)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    if args.command == 'test':
        test_convex_connection()
    
    elif args.command == 'list':
        # Determine sort order
        sort_by = 'mentions' if args.sort_mentions else 'sentiment'
        list_convex_analyses(timeframe=args.timeframe, limit=args.limit, sort_by=sort_by)
    
    elif args.command == 'show':
        show_convex_analysis(args.ticker.upper(), timeframe=args.timeframe)
    
    elif args.command == 'reeval':
        # Check setup
        is_setup, message = check_setup()
        if not is_setup:
            print(message)
            return
        
        if not os.getenv('OPENROUTER_API_KEY'):
            print(prompt_openrouter_setup())
            return
        
        model_manager = MultiModelManager(max_requests_per_day=args.max_requests)
        revaluate_stock(args.ticker.upper(), model_manager)


if __name__ == '__main__':
    main()

