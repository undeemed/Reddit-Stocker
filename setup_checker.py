"""Setup checker to guide users through configuration."""
import os
from pathlib import Path


def check_setup() -> tuple[bool, str]:
    """
    Check if the application is properly configured.
    
    Returns:
        (is_setup, message): Tuple of setup status and message
    """
    env_file = Path('.env')
    
    # Check if .env exists
    if not env_file.exists():
        return False, create_setup_guide("missing_env")
    
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Check Reddit credentials
    reddit_id = os.getenv('REDDIT_CLIENT_ID')
    reddit_secret = os.getenv('REDDIT_CLIENT_SECRET')
    reddit_agent = os.getenv('REDDIT_USER_AGENT')
    
    if not reddit_id or not reddit_secret:
        return False, create_setup_guide("missing_reddit")
    
    if not reddit_agent:
        return False, create_setup_guide("missing_user_agent")
    
    return True, "✅ Configuration complete!"


def create_setup_guide(issue_type: str) -> str:
    """Create a detailed setup guide based on the issue."""
    
    if issue_type == "missing_env":
        return """
╔══════════════════════════════════════════════════════════════════════════╗
║                         SETUP REQUIRED                                   ║
╚══════════════════════════════════════════════════════════════════════════╝

⚠️  Missing .env file

You need to create a .env file with your Reddit API credentials.

📝 STEP-BY-STEP SETUP:

1. Get Reddit API Credentials:
   
   a) Go to: https://www.reddit.com/prefs/apps
   b) Click "Create App" or "Create Another App"
   c) Fill in:
      • Name: StockReddit (or any name)
      • App type: Select "script"
      • Description: (optional)
      • About URL: (leave blank)
      • Redirect URI: http://localhost:8080
   d) Click "Create app"
   e) Copy your credentials:
      • CLIENT_ID: String under "personal use script"
      • CLIENT_SECRET: String next to "secret"

2. Create .env file:
   
   Create a file named ".env" in this directory with:
   
   REDDIT_CLIENT_ID=your_client_id_here
   REDDIT_CLIENT_SECRET=your_client_secret_here
   REDDIT_USER_AGENT=StockReddit/1.0
   
   (Optional - for AI features:)
   OPENROUTER_API_KEY=sk-or-v1-your-key-here

3. Run the script again!

Need help? Check the README.md file for detailed instructions.

╚══════════════════════════════════════════════════════════════════════════╝
"""
    
    elif issue_type == "missing_reddit":
        return """
╔══════════════════════════════════════════════════════════════════════════╗
║                    REDDIT CREDENTIALS MISSING                            ║
╚══════════════════════════════════════════════════════════════════════════╝

⚠️  Your .env file exists but is missing Reddit API credentials.

📝 WHAT TO DO:

1. Get Reddit API Credentials:
   
   • Go to: https://www.reddit.com/prefs/apps
   • Click "Create App" or "Create Another App"
   • Select "script" as the app type
   • Copy your CLIENT_ID and CLIENT_SECRET

2. Add to your .env file:
   
   REDDIT_CLIENT_ID=your_client_id_here
   REDDIT_CLIENT_SECRET=your_client_secret_here
   REDDIT_USER_AGENT=StockReddit/1.0

3. Save the file and run again!

Current .env location: {env_path}

╚══════════════════════════════════════════════════════════════════════════╝
""".format(env_path=Path('.env').absolute())
    
    elif issue_type == "missing_user_agent":
        return """
╔══════════════════════════════════════════════════════════════════════════╗
║                    USER AGENT MISSING                                    ║
╚══════════════════════════════════════════════════════════════════════════╝

⚠️  Your .env file is missing REDDIT_USER_AGENT.

📝 QUICK FIX:

Add this line to your .env file:

REDDIT_USER_AGENT=StockReddit/1.0

╚══════════════════════════════════════════════════════════════════════════╝
"""
    
    return "Unknown setup issue"


def prompt_openrouter_setup() -> str:
    """Prompt for OpenRouter setup for LLM features."""
    return """
╔══════════════════════════════════════════════════════════════════════════╗
║                    OPENROUTER API KEY MISSING                            ║
╚══════════════════════════════════════════════════════════════════════════╝

⚠️  This script requires OpenRouter API for AI-powered analysis.

📝 WHAT TO DO:

1. Get a FREE OpenRouter API Key:
   
   • Go to: https://openrouter.ai/keys
   • Sign up (free)
   • Create an API key
   • Copy your key (starts with sk-or-v1-)

2. Add to your .env file:
   
   OPENROUTER_API_KEY=sk-or-v1-your-key-here

3. Run this script again!

💡 TIP: OpenRouter offers FREE models (DeepSeek, Llama, etc.)
        You can use this script without paying anything!

Alternative: Use the basic version without AI:
   python stock_tracker.py          (instead of stock_tracker_llm.py)
   python sentiment_analyzer.py     (instead of sentiment_analyzer_llm.py)

╚══════════════════════════════════════════════════════════════════════════╝
"""


if __name__ == '__main__':
    # Test the setup checker
    is_setup, message = check_setup()
    print(message)
    if not is_setup:
        exit(1)

