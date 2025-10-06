"""
Aggregated LLM extraction - analyzes multiple posts at once.
Uses batched input with concise aggregated output (up to ~2K output tokens).
"""
import os
import json
import time
import requests
from typing import List, Dict, Set, Optional, Any
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
OPENROUTER_API_URL = 'https://openrouter.ai/api/v1/chat/completions'


def extract_tickers_aggregated(
    posts: List[str],
    model_manager: Any,
    valid_tickers: Optional[Set[str]] = None
) -> Dict:
    """
    Analyze multiple posts in ONE request and return aggregated results.
    
    Uses aggregated input and returns concise output (up to ~2K tokens) to maximize efficiency.
    
    Args:
        posts: List of post texts (already batched by caller)
        model_manager: MultiModelManager instance
        valid_tickers: Optional set of valid tickers for validation
        
    Returns:
        Dictionary with:
        {
            'tickers': {'AAPL': {'mentions': 5, 'sentiment': 0.65}, ...},
            'summary': 'Brief overall sentiment'
        }
    """
    if not posts:
        return {'tickers': {}, 'summary': ''}
    
    if not OPENROUTER_API_KEY:
        raise ValueError("OpenRouter API key not found in .env file")
    
    # Build mega-batch with all posts
    posts_text = "\n\n---POST SEPARATOR---\n\n".join([
        f"{text}"  # Full text, no truncation
        for text in posts
    ])
    
    # Keep prompt concise
    validation_hint = ""
    if valid_tickers:
        sample = sorted(list(valid_tickers))[:30]
        validation_hint = f"\nValid tickers: {', '.join(sample)}..."
    
    prompt = f"""Extract stock tickers and sentiment from {len(posts)} Reddit posts below.

RULES:
1. Only real stock tickers (AAPL, TSLA, etc) - ignore common words
2. Aggregate mentions across all posts
3. Calculate average sentiment per ticker: -1 (very negative) to +1 (very positive){validation_hint}

POSTS:
{posts_text}

OUTPUT (concise JSON only):
{{
  "tickers": {{
    "AAPL": {{"mentions": 3, "sentiment": 0.7}},
    "TSLA": {{"mentions": 5, "sentiment": -0.2}}
  }}
}}"""

    max_attempts = 5
    for attempt in range(max_attempts):
        try:
            # Get next model (returns single value, not tuple!)
            model = model_manager.get_next_model()
            
            if not model:
                # Brief wait until a model is available
                time.sleep(0.5)
                continue
            
            model_name = model.split('/')[-1]
            
            response = requests.post(
                OPENROUTER_API_URL,
                headers={
                    'Authorization': f'Bearer {OPENROUTER_API_KEY}',
                    'Content-Type': 'application/json',
                },
                json={
                    'model': model,
                    'messages': [{'role': 'user', 'content': prompt}],
                    'max_tokens': 2000,  # Concise output (~2K tokens)
                    'temperature': 0.1
                },
                timeout=60  # Longer timeout for big batch
            )
            
            if response.status_code == 429:
                model_manager.mark_rate_limited(model)
                # Immediately rotate to another model; no exponential backoff
                continue
            
            response.raise_for_status()
            model_manager.increment_request(model)
            
            result = response.json()
            
            if 'error' in result:
                print(f"⚠️  API error: {result['error'].get('message', 'Unknown')[:60]}")
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                return {'tickers': {}, 'summary': ''}
            
            if 'choices' not in result or not result['choices']:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                return {'tickers': {}, 'summary': ''}
            
            content = result['choices'][0]['message']['content'].strip()
            
            # Extract JSON
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()
            
            data = json.loads(content)
            tickers_data = data.get('tickers', {})
            
            # Validate tickers
            if valid_tickers:
                tickers_data = {
                    ticker: info
                    for ticker, info in tickers_data.items()
                    if ticker in valid_tickers
                }
            
            return {
                'tickers': tickers_data,
                'summary': data.get('summary', '')
            }
            
        except json.JSONDecodeError as e:
            # Rotate to another model on parse errors
            print(f"⚠️  JSON parse error on {model_name}; rotating model", flush=True)
            continue
        except requests.exceptions.Timeout:
            print(f"⚠️  Request timeout", flush=True)
            continue
        except Exception as e:
            print(f"⚠️  Error: {str(e)[:40]}", flush=True)
            if attempt < 2:
                time.sleep(1)
                continue
    
    return {'tickers': {}, 'summary': ''}

