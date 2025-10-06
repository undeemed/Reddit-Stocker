"""
LLM-based stock ticker extraction using OpenRouter API.
Provides context-aware extraction instead of regex pattern matching.
"""
import os
import json
import requests
import time
from typing import Set, List, Dict, Optional, Any
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
OPENROUTER_API_URL = 'https://openrouter.ai/api/v1/chat/completions'

# Default model - DeepSeek V3.1 is FREE and excellent (671B params, 163K context)
DEFAULT_MODEL = 'deepseek/deepseek-chat-v3.1:free'  # Free, high quality
# 
# Free models (9 total, all 100K+ context):
# 'deepseek/deepseek-chat-v3.1:free' - 671B params, 163K context (best)
# 'alibaba/tongyi-deepresearch-30b-a3b:free' - 30B params, reasoning
# 'meituan/longcat-flash-chat:free' - Fast, 100K+ context
# 'nvidia/nemotron-nano-9b-v2:free' - 9B params, efficient
# 'openai/gpt-oss-20b:free' - 20B params
# 'z-ai/glm-4.5-air:free' - 100K+ context
# 'deepseek/deepseek-r1-0528-qwen3-8b:free' - Reasoning model
# 'deepseek/deepseek-r1-0528:free' - Reasoning model
# 'meta-llama/llama-3.3-8b-instruct:free' - 8B params, 128K context


def extract_tickers_batch(
    texts: List[str],
    model_manager: Any,
    valid_tickers: Optional[Set[str]] = None
) -> List[Dict]:
    """
    Analyze multiple texts in one API call.
    More efficient and reduces hallucination via context.
    
    Args:
        texts: List of texts to analyze
        model_manager: MultiModelManager instance
        valid_tickers: Optional set of valid tickers for validation
        
    Returns:
        List of dictionaries with 'tickers' and 'context' for each text
    """
    if not texts:
        return []
    
    if not OPENROUTER_API_KEY:
        raise ValueError(
            "OpenRouter API key not found. "
            "Please set OPENROUTER_API_KEY in .env file"
        )
    
    # Build batch prompt
    comments_text = "\n\n".join([
        f"COMMENT {i+1}:\n{text[:500]}"  # Limit each to 500 chars
        for i, text in enumerate(texts)
    ])
    
    validation_hint = ""
    if valid_tickers:
        sample = sorted(list(valid_tickers))[:50]
        validation_hint = f"\n\nValid US stock tickers include: {', '.join(sample)}..."
    
    prompt = f"""You are a financial text analyzer. Extract stock tickers from these {len(texts)} Reddit comments.

IMPORTANT RULES:
1. Only extract actual stock ticker symbols (e.g., AAPL, TSLA, GME)
2. Ignore common words that aren't tickers (e.g., "I", "A", "FOR", "THE")
3. Consider context - is the person discussing the stock or just using the word?{validation_hint}

{comments_text}

Return JSON array with results for each comment:
{{
  "results": [
    {{"comment_id": 1, "tickers": ["AAPL"], "context": "positive discussion"}},
    {{"comment_id": 2, "tickers": [], "context": ""}}
  ]
}}

JSON response:"""

    # Retry with model rotation
    for attempt in range(3):
        model = model_manager.get_next_model()
        if not model:
            print(f"⚠️  No models available (all rate limited or budget exhausted)")
            return [{'tickers': [], 'budget_exhausted': True}] * len(texts)
        
        model_name = model.split('/')[-1]
        print(f"  → Using {model_name} for batch of {len(texts)} comments...", end='', flush=True)
        
        try:
            response = requests.post(
                OPENROUTER_API_URL,
                headers={
                    'Authorization': f'Bearer {OPENROUTER_API_KEY}',
                    'Content-Type': 'application/json',
                },
                json={
                    'model': model,
                    'messages': [{'role': 'user', 'content': prompt}],
                    'max_tokens': 800,
                    'temperature': 0.1
                },
                timeout=30
            )
            
            if response.status_code == 429:
                model_manager.mark_rate_limited(model)
                time.sleep(2 ** attempt)
                continue
            
            response.raise_for_status()
            model_manager.increment_request(model)
            
            # Parse response
            result = response.json()
            
            # Check for API errors
            if 'error' in result:
                print(f"⚠️  API error: {result['error'].get('message', 'Unknown')[:60]}")
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                return [{'tickers': [], 'context': {}}] * len(texts)
            
            # Check for empty response
            if 'choices' not in result or not result['choices']:
                print(f"⚠️  Empty response from {model_name}")
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                return [{'tickers': [], 'context': {}}] * len(texts)
            
            content = result['choices'][0]['message']['content'].strip()
            
            if not content:
                print(f"⚠️  Empty content from {model_name}")
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                return [{'tickers': [], 'context': {}}] * len(texts)
            
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()
            
            data = json.loads(content)
            results = data.get('results', [])
            
            # Validate tickers
            if valid_tickers:
                for result in results:
                    result['tickers'] = [t for t in result.get('tickers', []) if t in valid_tickers]
            
            # Pad results if needed
            while len(results) < len(texts):
                results.append({'tickers': [], 'context': ''})
            
            return results[:len(texts)]
            
        except json.JSONDecodeError as e:
            print(f" JSON error: {str(e)[:40]}!", flush=True)
            try:
                print(f"   Response preview: {str(response.content[:150])}...")
            except Exception:
                pass
            if attempt < 2:
                time.sleep(1)
                continue
        except requests.exceptions.Timeout:
            print(f" timeout!", flush=True)
            if attempt < 2:
                continue
        except requests.exceptions.RequestException as e:
            print(f" network error!", flush=True)
            if attempt < 2:
                time.sleep(1)
                continue
        except Exception as e:
            print(f" error: {str(e)[:50]}", flush=True)
            if attempt < 2:
                time.sleep(1)
                continue
    
    return [{'tickers': [], 'context': ''}] * len(texts)


def extract_tickers_with_llm(
    text: str,
    model_manager: Any,
    valid_tickers: Optional[Set[str]] = None
) -> Dict[str, Any]:
    """
    Extract stock tickers from text using LLM context understanding.
    
    Args:
        text: Text to analyze (post/comment)
        model_manager: MultiModelManager instance
        valid_tickers: Optional set of valid tickers for validation
        
    Returns:
        Dictionary with 'tickers' (list) and 'context' (dict of ticker->mentions)
    """
    if not OPENROUTER_API_KEY:
        raise ValueError(
            "OpenRouter API key not found. "
            "Please set OPENROUTER_API_KEY in .env file"
        )
    
    # Build validation hint if we have valid tickers
    validation_hint = ""
    if valid_tickers:
        sample_tickers = sorted(list(valid_tickers))[:100]  # Show sample
        validation_hint = f"\n\nValid US stock tickers include: {', '.join(sample_tickers[:50])}... (and {len(valid_tickers)} total)."
    
    prompt = f"""You are a financial text analyzer. Extract ALL stock ticker symbols mentioned in the following Reddit post/comment.

IMPORTANT RULES:
1. Only extract actual stock ticker symbols (e.g., AAPL, TSLA, GME)
2. Ignore common words that aren't tickers (e.g., "I", "A", "FOR", "THE")
3. Consider context - is the person discussing the stock or just using the word?
4. Include ticker even if it's part of a longer discussion
5. Return tickers in uppercase
6. If someone says "Apple" or "Tesla", include the ticker (AAPL, TSLA){validation_hint}

TEXT TO ANALYZE:
{text[:1000]}

Return your response as a JSON object with this exact format:
{{
  "tickers": ["AAPL", "TSLA"],
  "context": {{
    "AAPL": "positive discussion about earnings",
    "TSLA": "bearish sentiment on production"
  }}
}}

If no tickers found, return: {{"tickers": [], "context": {{}}}}

JSON response:"""

    # Retry with model rotation
    for attempt in range(3):
        model = model_manager.get_next_model()
        if not model:
            print(f"⚠️  No models available")
            return {'tickers': [], 'context': {}, 'budget_exhausted': True}
        
        model_name = model.split('/')[-1]
        print(f"  → {model_name}...", end='', flush=True)
        
        try:
            response = requests.post(
                OPENROUTER_API_URL,
                headers={
                    'Authorization': f'Bearer {OPENROUTER_API_KEY}',
                    'Content-Type': 'application/json',
                    'HTTP-Referer': 'https://github.com/your-repo/StockReddit',
                    'X-Title': 'StockReddit Analysis'
                },
                json={
                    'model': model,
                    'messages': [
                        {'role': 'user', 'content': prompt}
                    ],
                    'max_tokens': 500,
                    'temperature': 0.1  # Low temperature for consistent extraction
                },
                timeout=10
            )
            print(" ✓", flush=True)
            
            if response.status_code == 429:
                print(f" rate limited!", flush=True)
                model_manager.mark_rate_limited(model)
                if attempt < 2:
                    time.sleep(2 ** attempt)
                continue
            
            if response.status_code != 200:
                print(f"⚠️  HTTP {response.status_code} from {model.split('/')[-1]}")
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                return {'tickers': [], 'context': {}}
            
            model_manager.increment_request(model)
            result = response.json()
            
            # Check for API errors in response
            if 'error' in result:
                print(f"⚠️  API error from {model.split('/')[-1]}: {result['error'].get('message', 'Unknown error')[:60]}")
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                return {'tickers': [], 'context': {}}
            
            # Parse LLM response
            if 'choices' not in result or not result['choices']:
                print(f"⚠️  Empty response from {model.split('/')[-1]}")
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                return {'tickers': [], 'context': {}}
            
            content = result['choices'][0]['message']['content'].strip()
            
            if not content:
                print(f"⚠️  Empty content from {model.split('/')[-1]}")
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                return {'tickers': [], 'context': {}}
            
            # Extract JSON from response (handle markdown code blocks)
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()
            
            data = json.loads(content)
            
            # Validate against known tickers if provided
            if valid_tickers:
                validated_tickers = [t for t in data.get('tickers', []) if t in valid_tickers]
                validated_context = {k: v for k, v in data.get('context', {}).items() if k in valid_tickers}
                return {
                    'tickers': validated_tickers,
                    'context': validated_context
                }
            
            return {
                'tickers': data.get('tickers', []),
                'context': data.get('context', {})
            }
            
        except json.JSONDecodeError as e:
            # Log first 200 chars of response to debug
            try:
                content_preview = response.json() if hasattr(response, 'json') else str(response.content[:200])
                print(f"⚠️  JSON parse error from {model.split('/')[-1]}: {str(e)[:60]}")
                print(f"   Response preview: {str(content_preview)[:150]}...")
            except Exception:
                print(f"⚠️  JSON parse error from {model.split('/')[-1]}: {str(e)[:100]}")
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
        except requests.exceptions.Timeout:
            print(f"⚠️  Timeout from {model.split('/')[-1]}, retrying...")
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
        except requests.exceptions.RequestException as e:
            print(f"⚠️  Network error from {model.split('/')[-1]}: {str(e)[:100]}")
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
        except Exception as e:
            print(f"⚠️  Unexpected error: {str(e)[:100]}")
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
    
    return {'tickers': [], 'context': {}}


def batch_extract_tickers(
    texts: List[str],
    model: str = DEFAULT_MODEL,
    valid_tickers: Set[str] = None
) -> List[Dict[str, any]]:
    """
    Extract tickers from multiple texts.
    
    Args:
        texts: List of texts to analyze
        model: OpenRouter model to use
        valid_tickers: Optional set of valid tickers
        
    Returns:
        List of extraction results
    """
    results = []
    for text in texts:
        result = extract_tickers_with_llm(text, model, valid_tickers)
        results.append(result)
    
    return results


def get_available_models() -> List[str]:
    """Get list of recommended models for stock extraction."""
    return [
        # FREE MODELS (9 total, all 100K+ context)
        'deepseek/deepseek-chat-v3.1:free',  # 671B params, 163K context - BEST
        'alibaba/tongyi-deepresearch-30b-a3b:free',  # 30B params, reasoning
        'meituan/longcat-flash-chat:free',  # Fast, 100K+ context
        'nvidia/nemotron-nano-9b-v2:free',  # 9B params, efficient
        'openai/gpt-oss-20b:free',  # 20B params
        'z-ai/glm-4.5-air:free',  # 100K+ context
        'deepseek/deepseek-r1-0528-qwen3-8b:free',  # Reasoning, 8B
        'deepseek/deepseek-r1-0528:free',  # Reasoning model
        'meta-llama/llama-3.3-8b-instruct:free',  # 8B params, 128K context
        # PAID MODELS (Cheap to Expensive)
        'google/gemini-flash-1.5-8b',  # ~$0.04/1M tokens
        'openai/gpt-4o-mini',  # ~$0.15/1M tokens
        'anthropic/claude-3-5-haiku',  # ~$0.25/1M tokens
    ]


def estimate_cost(num_posts: int, avg_length: int = 500) -> Dict[str, float]:
    """
    Estimate API costs for different models.
    
    Args:
        num_posts: Number of posts to analyze
        avg_length: Average length of posts in characters
        
    Returns:
        Dictionary of model -> estimated cost in USD
    """
    # Rough token estimate: ~4 chars per token
    tokens_per_post = (avg_length + 500) / 4  # Input + prompt
    total_tokens = num_posts * tokens_per_post / 1_000_000  # Convert to millions
    
    # Approximate pricing (input tokens, per million)
    pricing = {
        'deepseek/deepseek-chat-v3.1:free': 0.00,
        'alibaba/tongyi-deepresearch-30b-a3b:free': 0.00,
        'meituan/longcat-flash-chat:free': 0.00,
        'nvidia/nemotron-nano-9b-v2:free': 0.00,
        'openai/gpt-oss-20b:free': 0.00,
        'z-ai/glm-4.5-air:free': 0.00,
        'deepseek/deepseek-r1-0528-qwen3-8b:free': 0.00,
        'deepseek/deepseek-r1-0528:free': 0.00,
        'meta-llama/llama-3.3-8b-instruct:free': 0.00,
        'google/gemini-flash-1.5-8b': 0.0375 * total_tokens,
        'openai/gpt-4o-mini': 0.15 * total_tokens,
        'anthropic/claude-3-5-haiku': 0.25 * total_tokens,
    }
    
    return pricing

