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

  📋 Utilities:
    setup              Run setup checker
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
            
        else:
            print(f"\n❌ Unknown command: {command}")
            print("\nAvailable commands:")
            print("  • track          - Track hot stocks (basic)")
            print("  • track-ai       - Track hot stocks (AI-powered)")
            print("  • analyze        - Analyze sentiment (basic)")
            print("  • analyze-ai     - Analyze sentiment (AI-powered)")
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

