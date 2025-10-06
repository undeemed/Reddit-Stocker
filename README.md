# Reddit Stocker - AI-Powered Reddit Stock Sentiment Analyzer

Track hot stocks and analyze sentiment across Reddit's top investing subreddits with context-aware AI and optional cloud storage.

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [Command Reference](#command-reference)
- [Convex Cloud Database](#convex-cloud-database-optional)
- [AI Models](#ai-models)
- [How It Works](#how-it-works)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)

## Features

- **Dual Mode Operation**: Fast regex or AI-powered context understanding
- **Smart Ticker Validation**: Auto-validates against 6,700+ real US stocks (NASDAQ, NYSE, AMEX)
- **Multi-Model AI**: Rotates through 27 free LLM models to avoid rate limits
- **Flexible Subreddit Selection**: Analyze 1-10 subreddits with ranges (e.g., `1-5`, `1,3,5`)
- **Intelligent Content Filtering**: Pre-filters low-value posts and meme comments before LLM (saves 50-70% on posts, 30-50% on comments)
- **Aggregated Batching**: Multiple posts combined per request with concise aggregated output (mentions + sentiment per ticker); output capped to ~2K tokens
- **Budget Tracking**: Built-in request budget system for cost control
- **Cloud Database (Optional)**: Real-time sync, historical tracking, AI re-evaluation

## Quick Start

### 1. Setup - download zip and open

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On macOS/Linux
# or .venv\Scripts\activate on Windows

# Install Python dependencies
pip install -r requirements.txt
```

### 2. Configure Reddit API

Create a `.env` file in the project root:

```env
# Reddit API (Required - Get from https://www.reddit.com/prefs/apps)
REDDIT_CLIENT_ID=your_client_id_here
REDDIT_CLIENT_SECRET=your_client_secret_here
REDDIT_USER_AGENT=StockReddit/1.0

# OpenRouter API (Optional - For AI features, Get from https://openrouter.ai/keys)
OPENROUTER_API_KEY=sk-or-v1-your-key-here

# Convex Database (Optional - For cloud storage, see section below)
CONVEX_URL=https://your-deployment.convex.cloud
```

**Get Reddit API Credentials:**

1. Go to https://www.reddit.com/prefs/apps
2. Click "Create App" → Select "script" type
3. Copy the client ID and secret

### 3. Run Analysis

```bash
# Activate environment
source .venv/bin/activate

# Check setup
python run.py setup

# Track hot stocks (basic - fast, no API costs)
python run.py track

# Track hot stocks with AI (accurate, context-aware)
python run.py track-ai -tm -pl 20 -as   # -as auto-analyzes sentiment for top 3

# Analyze sentiment for a stock
python run.py analyze-ai AAPL
```

## Command Reference

### Core Commands

```bash
# Show all commands
python run.py help

# Track hot stocks
python run.py track              # Basic (fast, free)
python run.py track-ai [OPTIONS] # AI-powered (accurate)

# Analyze sentiment
python run.py analyze TICKER              # Basic
python run.py analyze-ai TICKER [OPTIONS] # AI-powered

# Convex database (if configured)
python run.py convex-list        # List analyses (sorted by sentiment)
python run.py convex-list -m     # List analyses (sorted by mentions)
python run.py convex-show TICKER # Show details for a ticker

# Utilities
python run.py setup              # Check configuration
python run.py track-ai -ls       # List available subreddits
python run.py track-ai -lm       # List AI models
```

### Track Hot Stocks Options

```bash
python run.py track-ai [OPTIONS]

Options:
  -t,  --timeframe {day,week,month}  Time period (default: day)
  -tm, --test-mode                   Test with only r/wallstreetbets
  -s,  --subreddits TEXT             Select subreddits (e.g., "1-5", "1,3,5")
  -pl, --post-limit INT              Posts per subreddit (default: 100)
  -tc, --top-comments INT            Comments to analyze (default: 50)
  -bs, --batch-size INT              Comments per LLM batch (default: 50)
  -as, --analyze-sentiment           Auto-analyze sentiment for top stocks
  -an, --analyze-top-n INT           Number of top stocks to analyze (default: 3)
  -mr, --max-requests INT            Daily request limit (default: 1000)

Examples:
  python run.py track-ai -tm -pl 20           # Test mode, 20 posts (mentions only)
  python run.py track-ai -tm -pl 20 -as       # Test + auto-analyze sentiment
  python run.py track-ai -s 1-3 -pl 50 -as -an 5  # Top 5 with sentiment
  python run.py track-ai -t week -s 1,3,5     # Weekly, specific subreddits
```

### Analyze Sentiment Options

```bash
python run.py analyze-ai TICKER [OPTIONS]

Options:
  -tm, --test-mode                   Test with only r/wallstreetbets
  -s,  --subreddits TEXT             Select subreddits (e.g., "1-5", "1,3,5")
  -mr, --max-requests INT            Daily request limit (default: 1000)

Examples:
  python run.py analyze-ai AAPL               # All subreddits
  python run.py analyze-ai TSLA -tm           # Test mode
  python run.py analyze-ai NVDA -s 1-3        # First 3 subreddits
```

### Subreddit Selection

View available subreddits: `python run.py track-ai -ls`

**Selection patterns:**

- Single: `-s 1` → r/wallstreetbets only
- Range: `-s 1-5` → First 5 subreddits
- Multiple: `-s 1,3,5` → Subreddits #1, #3, #5
- Mixed: `-s 1-3,7,9` → Subreddits #1-3, #7, #9

**Available subreddits:**

1. r/wallstreetbets
2. r/stocks
3. r/investing
4. r/StockMarket
5. r/options
6. r/pennystocks
7. r/Daytrading
8. r/swingtrading
9. r/RobinHood
10. r/SecurityAnalysis

## Convex Cloud Database (Optional)

Convex provides real-time cloud storage with advanced features. **Completely optional** - the app works perfectly with SQLite alone.

### Benefits

- ☁️ **Cloud Access** - View analyses from any device
- 📊 **Real-time Sync** - Data updates instantly across devices
- 📈 **Historical Tracking** - Automatic version control and trend analysis
- 🔄 **AI Re-evaluation** - Re-analyze stored data with updated models
- 👥 **Team Sharing** - Collaborate with shared deployment
- 🆓 **Free Tier** - 1M calls/month, 1GB storage (sufficient for most users)

### Quick Setup (5 minutes)

**Prerequisites:** Node.js 18+ installed ([download](https://nodejs.org))

```bash
# 1. Install Node dependencies
npm install

# 2. Initialize Convex (opens browser for GitHub login)
npx convex dev
# → Login with GitHub
# → Create new project
# → Keep terminal running

# 3. Add URL to .env file
# Copy CONVEX_URL from .env.local to .env
cat .env.local  # View the auto-generated URL
# Add to .env: CONVEX_URL=https://your-deployment.convex.cloud

# 4. Test connection
python run.py convex-test
```

### Convex Commands

```bash
# Test connection
python run.py convex-test

# List all stored analyses (sorted by sentiment strength by default)
python run.py convex-list
python run.py convex-list -m          # Sort by mentions instead
python run.py convex-list -t day -m   # Filter by timeframe, sort by mentions

# Show detailed analysis for a ticker
python run.py convex-show AAPL

# Re-evaluate with fresh AI (uses stored raw data)
python run.py convex-reeval AAPL
```

#### Weighted Sentiment Score (Used in Lists)

Convex stores both the raw average sentiment and a weighted sentiment score shown by `convex-list` when available.

- Formula: `sentimentScore = ((positive - negative) / max(1, totalVotes)) * log(1 + totalMentions)`
- Where:
  - `positive`, `neutral`, `negative` are post counts from analysis
  - `totalVotes = positive + neutral + negative`
  - `totalMentions` is the overall mention volume

This favors strongly directional sentiment with higher discussion volume. If `sentimentScore` is missing, the view falls back to the simple average sentiment.

**Convex List Options:**

- `-m, --sort-mentions` - Sort by mention count (highest first)
- `-s, --sort-sentiment` - Sort by sentiment strength (default)
- `-t, --timeframe` - Filter by timeframe (day, week, month)
- `-l, --limit` - Maximum results to show (default: 20)

**Examples:**

```bash
# Default: sorted by strongest sentiment (positive or negative)
python run.py convex-list

# Sort by which stocks are mentioned most
python run.py convex-list -m

# Show only today's analyses, sorted by mentions
python run.py convex-list -t day -m

# Show top 5 by sentiment
python run.py convex-list -l 5
```

### How It Works

Once configured, analyses automatically save to Convex when you run:

```bash
python run.py track-ai -tm -pl 20      # Auto-saves to cloud
python run.py analyze-ai AAPL          # Auto-saves to cloud
```

**AI Re-evaluation:**

```bash
# Re-analyze stored data with updated AI models
python run.py convex-reeval AAPL

# This will:
# - Retrieve raw post data from cloud
# - Re-extract context with current AI
# - Recalculate sentiment scores
# - Generate new AI summary
# - Increment analysis version
# - Show before/after comparison
```

### Python API

Use the Convex client directly in your code:

```python
from convex_client import StockConvexClient

client = StockConvexClient()

# Get analysis
analysis = client.get_analysis("AAPL", timeframe="day")
print(f"Sentiment: {analysis['averageSentiment']}")

# Get top stocks
top_stocks = client.get_top_stocks(timeframe="day", limit=10)

# Get historical data
history = client.get_history("AAPL", limit=30)

# Real-time subscription
for update in client.subscribe_to_analysis("AAPL"):
    print(f"Updated: {update['averageSentiment']}")
```

### Convex Pricing

**Free Tier (sufficient for most users):**

- 1M function calls/month
- 1GB storage
- 1GB bandwidth

**Typical usage:** 10 stocks/day = ~300 calls/month (well within free tier)

**Resources:**

- [Convex Dashboard](https://dashboard.convex.dev) - View data in browser
- [Convex Docs](https://docs.convex.dev/quickstart/python) - Full documentation
- [Convex Discord](https://convex.dev/community) - Get help

## AI Models

The LLM version rotates through **27 free models** with 100K+ context windows (higher throughput, fewer rate limits). Examples include:

- DeepSeek V3.1, DeepSeek R1, DeepSeek R1 Qwen3
- Meta Llama 3.3/4 (Maverick/Scout)
- Qwen3 (coder, 235B A22B)
- Mistral Small 3.1/3.2 24B, Mistral Nemo
- Moonshot Kimi Dev 72B / VL A3B Thinking
- Google Gemini 2.0 Flash Exp, Gemma 3 27B
- NVIDIA Nemotron Nano, OpenAI GPT-OSS 20B, Z-AI GLM 4.5 Air

### OpenRouter Rate Limits (Important)

There are platform rate limits for requests to models served via OpenRouter, regardless of account status:

- Free usage limits (models with IDs ending in `:free`): up to 20 requests per minute
- Daily limits for `:free` models:
  - If you have purchased less than 10 credits: limited to 50 requests per day
  - If you have purchased at least 10 credits: increased to 1000 requests per day

See the OpenRouter documentation for details and the most up-to-date limits: https://openrouter.ai/docs

**Why multiple models?** Automatic failover, load distribution, 24/7 availability, all free!

## How It Works

### Ticker Validation

1. Fetches real stock symbols from [US-Stock-Symbols](https://github.com/rreichel3/US-Stock-Symbols)
2. Covers NASDAQ (~4,000), NYSE (~3,100), AMEX (~300)
3. Cached locally for 24 hours
4. Eliminates false positives (no tracking "CEO", "NEW", "FOR" as tickers)

### AI Context Understanding

**Without AI (Regex):**

- "I love FOR loops" → Incorrectly extracts $FOR ❌
- "YOLO on TSLA puts" → Extracts TSLA but misses bearish context ⚠️

**With AI (LLM):**

- "I love FOR loops" → Correctly ignores (programming) ✅
- "YOLO on TSLA puts" → Extracts TSLA + bearish sentiment ✅

**Smart Content Filtering:**

Automatically filters out low-value content **BEFORE** sending to LLM:

**Post Pre-Filter:**

- Posts with <10 upvotes → SKIPPED (low engagement)
- Posts without likely tickers → SKIPPED (off-topic)
- Posts tagged "Gain/Loss/Meme" → SKIPPED (screenshots/jokes)
- **Result:** ~50-70% of posts filtered before LLM

**Intelligent Post Batching:**

- Batches posts up to ~98K tokens per API call (maximizing 100K+ context windows)
- Example: 30-40 posts in 1 request instead of 30-40 separate requests
- **Result:** 30-40x fewer API requests for posts

**Comment Quality Filter:**

- "to the moon!!! 🚀🚀🚀" → SKIPPED (meme)
- "YOLO" → SKIPPED (low-effort)
- "F" → SKIPPED (spam)
- Pure emojis → SKIPPED
- **Result:** 30-50% fewer API requests for comments

**Kept (valuable analysis):**

- "Strong Q4 earnings with 15% revenue growth" → ANALYZED ✅
- "Company guidance raised to $5.2B for FY2025" → ANALYZED ✅
- "Analyst upgraded to buy with $150 target" → ANALYZED ✅
- "High debt levels and declining market share" → ANALYZED ✅

**Combined Result:** 50-100x fewer API requests overall!

### Efficiency

- **Post Pre-Filter**: Skips low-score posts (<10 upvotes) and posts without tickers (saves 50-70% of post requests)
- **Comment Quality Filter**: Filters memes/spam before LLM (saves 30-50% of comment requests)
- **Comment Batch Processing**: Multi-comments per API request (50x more efficient)
- **Smart Sorting**: Uses Reddit's native top comment sorting
- **Budget Tracking**: Persistent daily request limits
- **Overall**: ~20-30 API requests vs 2000+ for 100 posts with 50 comments each

## Database

**Local SQLite (Default):**

- `stocks.db` - All mentions and sentiment data
- `stock_mentions` table - Ticker mentions with timestamps
- `stock_sentiment` table - Sentiment scores

**Cloud Convex (Optional):**

- `stockAnalyses` - Complete analyses with AI insights + raw data
- `stockHistory` - Historical snapshots for trend analysis
- `revaluationQueue` - AI re-evaluation request tracking

**Query SQLite:**

```bash
sqlite3 stocks.db "SELECT * FROM stock_mentions WHERE ticker='AAPL' LIMIT 10;"
```

## Configuration

### Environment Variables

| Variable                 | Required    | Description                            |
| ------------------------ | ----------- | -------------------------------------- |
| `REDDIT_CLIENT_ID`     | Yes         | Reddit API client ID                   |
| `REDDIT_CLIENT_SECRET` | Yes         | Reddit API secret                      |
| `REDDIT_USER_AGENT`    | Yes         | Bot identifier (e.g., StockReddit/1.0) |
| `OPENROUTER_API_KEY`   | Recommended | For AI features                        |
| `CONVEX_URL`           | Optional    | For cloud database                     |

### Generated Files

- `stocks.db` - SQLite database
- `valid_tickers_cache.json` - Cached stock symbols (24h)
- `request_budget.json` - Daily AI request tracking
- `.env.local` - Convex environment (auto-generated)

## Performance

**Speed:**

- Basic: ~10 seconds per subreddit
- AI: ~30 seconds per subreddit (API calls)

**Accuracy:**

- Basic: ~85% (false positives on word matches)
- AI: ~98% (context-aware extraction)

**Cost:**

- Basic: $0 (completely free)
- AI: $0 with free models

## Troubleshooting

### Setup Issues

**"No module named 'praw'"**

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

**"Reddit API credentials not found"**

```bash
python run.py setup  # Check configuration
```

- Verify `.env` file exists in project root
- Check credentials are correct (no quotes around values)

**"No valid tickers found"**

- First run fetches from GitHub (~2-3 seconds)
- Check internet connection
- Cache expires after 24 hours (auto-refresh)

### AI Issues

**"Rate limit exceeded"**

- Free models have rate limits
- Script automatically switches models
- Use `-mr 500` to set lower daily budget (refer to openrouter api limits)

**"JSON parse errors"**

- Normal with free AI models under load
- Script retries automatically
- Doesn't affect results

### Convex Issues

**"CONVEX_URL not found"**

1. Run `npx convex dev`
2. Copy `CONVEX_URL` from `.env.local` to `.env`
3. Test: `python run.py convex-test`

**"Connection failed"**

- Ensure `npx convex dev` is running in another terminal
- Check internet connection
- Verify URL in `.env` is correct

**"No data found"**

- Run an analysis first: `python run.py track-ai -tm -pl 20`

## Usage Tips

### Start Small

```bash
# Test with minimal requests
python run.py track-ai -tm -pl 10

# Scale up gradually
python run.py track-ai -tm -pl 50
python run.py track-ai -s 1-5 -pl 100
```

### Monitor Budget

The script shows real-time usage:

```
📊 Budget: 127/1000 requests (12.7%)
🚨 Budget warning: 85% used
```

### Error Handling

Some free AI models may occasionally fail:

- Script automatically retries with different models
- Errors are logged but don't stop execution
- 9 models ensure high availability

## License

MIT License - Feel free to use and modify!

## Support

For issues:

1. Check setup: `python run.py setup`
2. Try test mode: `python run.py track-ai -tm -pl 10`
3. Verify `.env` configuration
4. Check this README
5. Open a GitHub issue

## Contributing

Found a bug or want to add features? Pull requests welcome!

---

**Version:** 1.1.0
**Updated:** October 2025
**What's New:** Convex cloud database integration with AI re-evaluation and batch processing
