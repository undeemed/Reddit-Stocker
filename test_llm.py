"""
Quick test to demonstrate LLM extraction vs regex.
Run this to see the difference in accuracy.
"""
from llm_extractor import extract_tickers_with_llm
from reddit_client import extract_tickers
from ticker_validator import fetch_valid_tickers

# Test posts with tricky cases
test_posts = [
    """
    I think AAPL is great FOR long term investment. The CEO said they will 
    focus on AI, and TSLA might be competition BUT Apple has better margins.
    NEW products coming soon!
    """,
    
    """
    GME to the moon! 🚀 I bought more shares TODAY at the dip. 
    This IS going to squeeze again, mark my words. ALL in!
    """,
    
    """
    Just sold my NVDA position. Made a killing on the AI boom.
    Looking at AMD next, they have better value IMO.
    """
]

print("="*70)
print("TESTING: Regex vs LLM Stock Extraction")
print("="*70)

valid_tickers = fetch_valid_tickers()

for i, post in enumerate(test_posts, 1):
    print(f"\n📝 TEST POST #{i}:")
    print("-" * 70)
    print(post.strip())
    print("-" * 70)
    
    # Regex extraction
    regex_tickers = extract_tickers(post, valid_tickers)
    print(f"\n🔤 REGEX METHOD:")
    print(f"   Found: {sorted(regex_tickers)}")
    
    # LLM extraction (requires API key)
    try:
        llm_result = extract_tickers_with_llm(post, valid_tickers=valid_tickers)
        print(f"\n🤖 LLM METHOD:")
        print(f"   Found: {sorted(llm_result['tickers'])}")
        if llm_result['context']:
            print(f"   Context:")
            for ticker, context in llm_result['context'].items():
                print(f"      • {ticker}: {context[:80]}...")
    except Exception as e:
        print(f"\n🤖 LLM METHOD:")
        print(f"   ⚠️  Skipped (API key needed): {str(e)[:50]}")
    
    print()

print("="*70)
print("SUMMARY")
print("="*70)
print("""
Regex Method:
  ✅ Fast (no API calls)
  ✅ Free
  ❌ Gets false positives (CEO, FOR, NEW, etc.)
  ❌ No context understanding

LLM Method:
  ✅ High accuracy
  ✅ Context understanding
  ✅ Filters false positives
  ❌ Requires API key
  ❌ Costs money (or use free tier)
  
Recommendation: Use regex for speed, LLM for accuracy
""")
print("="*70)

