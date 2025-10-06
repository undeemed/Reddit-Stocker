#!/usr/bin/env python3
"""
Unified entry point for StockReddit scripts.

Usage:
    python run.py track [OPTIONS]              # Track hot stocks (basic)
    python run.py track-ai [OPTIONS]           # Track hot stocks (AI-powered)
    python run.py analyze TICKER [OPTIONS]     # Analyze sentiment (basic)
    python run.py analyze-ai TICKER [OPTIONS]  # Analyze sentiment (AI-powered)
    
Examples:
    python run.py track --timeframe day
    python run.py track-ai -tm -pl 50
    python run.py analyze AAPL
    python run.py analyze-ai TSLA -s 1-5
"""
import sys
import argparse


def show_help():
    """Display help information."""
    help_text = """
╔══════════════════════════════════════════════════════════════════════════╗
║                        StockReddit Commands                              ║
╚══════════════════════════════════════════════════════════════════════════╝

USAGE:
    python run.py <command> [arguments]

COMMANDS:

  📊 Track Hot Stocks:
    track              Track hot stocks across Reddit (basic, fast)
    track-ai           Track hot stocks with AI context (accurate)

  📈 Analyze Sentiment:
    analyze TICKER     Analyze sentiment for a stock (basic, fast)
    analyze-ai TICKER  Analyze sentiment with AI context (accurate)

  🗄️  Convex Database:
    convex-test        Test Convex connection
    convex-list        List all analyses (sorted by sentiment)
                         -m: sort by mentions | -t: filter timeframe
    convex-show TICKER Show detailed analysis for a ticker
    convex-reeval TICKER Re-evaluate stock with AI

  📋 Utilities:
    setup              Run setup checker
    budget            Set or view daily LLM request budget
    help               Show this help message

EXAMPLES:

  # Track hot stocks today (basic)
  python run.py track

  # Track hot stocks with AI (test mode, 20 posts)
  python run.py track-ai -tm -pl 20

  # Analyze Apple sentiment (basic)
  python run.py analyze AAPL

  # Analyze Tesla with AI on specific subreddits
  python run.py analyze-ai TSLA -s 1-3

  # List available subreddits
  python run.py track-ai -ls

  # Show AI models
  python run.py track-ai -lm

  # Convex database operations
  python run.py convex-test
  python run.py convex-list           # Sorted by sentiment
  python run.py convex-list -m        # Sorted by mentions
  python run.py convex-show AAPL
  python run.py convex-reeval AAPL

FOR MORE OPTIONS:
    python run.py track --help
    python run.py track-ai --help
    python run.py analyze --help
    python run.py analyze-ai --help

DOCUMENTATION:
    See README.md for detailed usage and setup instructions

╚══════════════════════════════════════════════════════════════════════════╝
"""
    print(help_text)


def main():
    """Main entry point."""
    
    # If no arguments or help requested, show help
    if len(sys.argv) < 2 or sys.argv[1] in ['-h', '--help', 'help']:
        show_help()
        sys.exit(0)
    
    command = sys.argv[1]
    
    # Remove the command from sys.argv so the script gets the right args
    sys.argv = [sys.argv[0]] + sys.argv[2:]
    
    try:
        if command == 'track':
            # Basic stock tracker
            from stock_tracker import main as tracker_main
            tracker_main()
            
        elif command == 'track-ai':
            # AI-powered stock tracker
            from stock_tracker_llm import main as tracker_llm_main
            tracker_llm_main()
            
        elif command == 'analyze':
            # Basic sentiment analyzer
            if len(sys.argv) < 2:
                print("\n❌ Error: Missing ticker symbol")
                print("Usage: python run.py analyze TICKER [OPTIONS]")
                print("Example: python run.py analyze AAPL\n")
                sys.exit(1)
            from sentiment_analyzer import main as analyzer_main
            analyzer_main()
            
        elif command == 'analyze-ai':
            # AI-powered sentiment analyzer
            if len(sys.argv) < 2:
                print("\n❌ Error: Missing ticker symbol")
                print("Usage: python run.py analyze-ai TICKER [OPTIONS]")
                print("Example: python run.py analyze-ai AAPL -s 1-5\n")
                sys.exit(1)
            from sentiment_analyzer_llm import main as analyzer_llm_main
            analyzer_llm_main()
            
        elif command == 'setup':
            # Run setup checker
            from setup_checker import check_setup
            is_setup, message = check_setup()
            print(message)
            if is_setup:
                print("\n✅ All set! You can now run:")
                print("  • python run.py track")
                print("  • python run.py track-ai")
                print("  • python run.py analyze AAPL")
                print("  • python run.py analyze-ai AAPL\n")
            sys.exit(0 if is_setup else 1)

        elif command == 'budget':
            # Set or view daily LLM request budget
            import argparse
            from llm_manager import MultiModelManager
            parser = argparse.ArgumentParser(description='Set or view daily LLM request budget')
            parser.add_argument('-s', '--set', type=int, help='Set daily request budget (e.g., 500)')
            parser.add_argument('-r', '--reset', action='store_true', help='Reset usage counters for the new day')
            args = parser.parse_args(sys.argv[1:])

            manager = MultiModelManager()
            if args.set is not None:
                try:
                    manager.set_limit(args.set)
                    print(f"✅ Budget limit set to {args.set} requests/day")
                except Exception as e:
                    print(f"❌ Failed to set budget: {e}")
                    sys.exit(1)
            if args.reset:
                manager.reset_budget()
                print("✅ Budget usage reset for the new day")
            # Always show current status
            print(f"Current budget: {manager.get_stats()}")
            sys.exit(0)
        
        elif command == 'convex-test':
            # Test Convex connection
            from convex_client import test_convex_connection
            test_convex_connection()
        
        elif command == 'convex-list':
            # List Convex analyses
            from convex_tracker import list_convex_analyses
            
            # Parse args for sorting
            import argparse
            parser = argparse.ArgumentParser()
            parser.add_argument('-t', '--timeframe', help='Filter by timeframe')
            parser.add_argument('-l', '--limit', type=int, default=20, help='Result limit')
            parser.add_argument('-m', '--sort-mentions', action='store_true', help='Sort by mentions')
            parser.add_argument('-s', '--sort-sentiment', action='store_true', help='Sort by sentiment')
            args = parser.parse_args(sys.argv[1:])
            
            sort_by = 'mentions' if args.sort_mentions else 'sentiment'
            list_convex_analyses(timeframe=args.timeframe, limit=args.limit, sort_by=sort_by)
        
        elif command == 'convex-show':
            # Show Convex analysis
            if len(sys.argv) < 2:
                print("\n❌ Error: Missing ticker symbol")
                print("Usage: python run.py convex-show TICKER")
                print("Example: python run.py convex-show AAPL\n")
                sys.exit(1)
            from convex_tracker import show_convex_analysis
            ticker = sys.argv[1].upper()
            show_convex_analysis(ticker)
        
        elif command == 'convex-reeval':
            # Re-evaluate with AI
            if len(sys.argv) < 2:
                print("\n❌ Error: Missing ticker symbol")
                print("Usage: python run.py convex-reeval TICKER")
                print("Example: python run.py convex-reeval AAPL\n")
                sys.exit(1)
            from convex_tracker import revaluate_stock
            from llm_manager import MultiModelManager
            import os
            from setup_checker import check_setup, prompt_openrouter_setup
            
            is_setup, message = check_setup()
            if not is_setup:
                print(message)
                sys.exit(1)
            
            if not os.getenv('OPENROUTER_API_KEY'):
                print(prompt_openrouter_setup())
                sys.exit(1)
            
            ticker = sys.argv[1].upper()
            model_manager = MultiModelManager()
            revaluate_stock(ticker, model_manager)
            
        else:
            print(f"\n❌ Unknown command: {command}")
            print("\nAvailable commands:")
            print("  • track          - Track hot stocks (basic)")
            print("  • track-ai       - Track hot stocks (AI-powered)")
            print("  • analyze        - Analyze sentiment (basic)")
            print("  • analyze-ai     - Analyze sentiment (AI-powered)")
            print("  • convex-test    - Test Convex connection")
            print("  • convex-list    - List Convex analyses")
            print("  • convex-show    - Show Convex analysis")
            print("  • convex-reeval  - Re-evaluate with AI")
            print("  • setup          - Check configuration")
            print("  • help           - Show help")
            print("\nRun 'python run.py help' for more information\n")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

