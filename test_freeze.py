"""Quick diagnostic to find where the script freezes."""
import sys

print("1. Testing imports...")
sys.stdout.flush()

try:
    from dotenv import load_dotenv
    print("   ✓ dotenv imported")
    sys.stdout.flush()
    
    load_dotenv()
    print("   ✓ .env loaded")
    sys.stdout.flush()
    
    import os
    reddit_id = os.getenv('REDDIT_CLIENT_ID')
    reddit_secret = os.getenv('REDDIT_CLIENT_SECRET')
    openrouter_key = os.getenv('OPENROUTER_API_KEY')
    
    print(f"   Reddit ID: {'SET' if reddit_id and reddit_id != 'your_client_id_here' else 'MISSING'}")
    print(f"   Reddit Secret: {'SET' if reddit_secret and reddit_secret != 'your_client_secret_here' else 'MISSING'}")
    print(f"   OpenRouter Key: {'SET' if openrouter_key and openrouter_key != 'your_openrouter_key_here' else 'MISSING'}")
    sys.stdout.flush()
    
except Exception as e:
    print(f"   ✗ Error: {e}")
    sys.exit(1)

print("\n2. Testing Reddit client...")
sys.stdout.flush()

try:
    import praw
    print("   ✓ praw imported")
    sys.stdout.flush()
    
    reddit = praw.Reddit(
        client_id=reddit_id,
        client_secret=reddit_secret,
        user_agent='StockReddit/1.0'
    )
    print("   ✓ Reddit client created")
    sys.stdout.flush()
    
    # Try to access Reddit (this will hang if credentials are wrong)
    import signal
    
    def timeout_handler(signum, frame):
        raise TimeoutError("Reddit API timeout")
    
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(10)  # 10 second timeout
    
    try:
        subreddit = reddit.subreddit('wallstreetbets')
        _ = subreddit.display_name  # This forces API call
        print("   ✓ Reddit API working")
        sys.stdout.flush()
    except TimeoutError:
        print("   ✗ Reddit API TIMEOUT (credentials likely invalid)")
        sys.exit(1)
    except Exception as e:
        print(f"   ✗ Reddit API error: {e}")
        sys.exit(1)
    finally:
        signal.alarm(0)
        
except Exception as e:
    print(f"   ✗ Error: {e}")
    sys.exit(1)

print("\n3. Testing ticker validator...")
sys.stdout.flush()

try:
    from ticker_validator import fetch_valid_tickers
    print("   ✓ ticker_validator imported")
    sys.stdout.flush()
    
    # This might hang on GitHub API call
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(15)  # 15 second timeout for GitHub
    
    try:
        tickers = fetch_valid_tickers()
        print(f"   ✓ Loaded {len(tickers)} tickers")
        sys.stdout.flush()
    except TimeoutError:
        print("   ✗ GitHub API TIMEOUT (network issue)")
        sys.exit(1)
    finally:
        signal.alarm(0)
        
except Exception as e:
    print(f"   ✗ Error: {e}")
    sys.exit(1)

print("\n4. Testing LLM manager...")
sys.stdout.flush()

try:
    from llm_manager import MultiModelManager
    manager = MultiModelManager(max_requests_per_day=10)
    print(f"   ✓ LLM manager created: {manager.get_stats()}")
    sys.stdout.flush()
except Exception as e:
    print(f"   ✗ Error: {e}")
    sys.exit(1)

print("\nAll passed. The freeze is likely in the main analysis loop.")
print("Try running with very low limits: --post-limit 1 --top-comments 1")

