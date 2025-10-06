"""
Multi-Model Manager for OpenRouter API.
Handles round-robin model rotation, rate limiting, and request budget tracking.
"""
import json
import time
from datetime import datetime
from typing import List, Optional, Dict


class MultiModelManager:
    """Manages multiple LLM models with round-robin rotation and rate limiting."""
    
    def __init__(self, models: Optional[List[str]] = None, max_requests_per_day: int = 1000):
        """
        Initialize the multi-model manager.
        
        Args:
            models: List of model identifiers to rotate through
            max_requests_per_day: Maximum requests allowed per day
        """
        self.models = models or [
            # Rotate through models to bypass limiting
            'deepseek/deepseek-chat-v3.1:free',
            'alibaba/tongyi-deepresearch-30b-a3b:free',
            'meituan/longcat-flash-chat:free',
            'nvidia/nemotron-nano-9b-v2:free',
            'openai/gpt-oss-20b:free',
            'z-ai/glm-4.5-air:free',
            'deepseek/deepseek-r1-0528-qwen3-8b:free',
            'deepseek/deepseek-r1-0528:free',
            'meta-llama/llama-3.3-8b-instruct:free',
            'qwen/qwen3-coder:free',
            'tngtech/deepseek-r1t2-chimera:free',
            'mistralai/mistral-small-3.2-24b-instruct:free',
            'moonshotai/kimi-dev-72b:free',
            'qwen/qwen3-235b-a22b:free',
            'tngtech/deepseek-r1t-chimera:free',
            'microsoft/mai-ds-r1:free',
            'moonshotai/kimi-vl-a3b-thinking:free',
            'meta-llama/llama-4-maverick:free',
            'meta-llama/llama-4-scout:free',
            'deepseek/deepseek-chat-v3-0324:free',
            'mistralai/mistral-small-3.1-24b-instruct:free',
            'google/gemma-3-27b-it:free',
            'nousresearch/deephermes-3-llama-3-8b-preview:free',
            'deepseek/deepseek-r1:free',
            'google/gemini-2.0-flash-exp:free',
            'meta-llama/llama-3.2-3b-instruct:free',
            'mistralai/mistral-nemo:free',
        ]
        self.current_index = 0
        self.rate_limited: Dict[str, float] = {}  # model -> timestamp when rate limit expires
        # Per-model pacing to align with 20 req/min/model for :free variants
        self.requests_per_minute: float = 20.0
        self.min_interval: float = 60.0 / self.requests_per_minute  # ~3.0s
        self.last_request_time: Dict[str, float] = {}
        self.max_requests = max_requests_per_day
        self.budget = self.load_budget()
        # Ensure persisted limit aligns with constructor override
        if self.budget.get('limit') != self.max_requests:
            self.budget['limit'] = self.max_requests
            self.save_budget()
        
    def load_budget(self) -> dict:
        """Load budget from file or create new if doesn't exist."""
        try:
            with open('request_budget.json', 'r') as f:
                data = json.load(f)
                # Reset if different day
                if data['date'] != datetime.now().strftime('%Y-%m-%d'):
                    return self.reset_budget()
                return data
        except (FileNotFoundError, json.JSONDecodeError):
            return self.reset_budget()
    
    def reset_budget(self) -> dict:
        """Reset budget for a new day."""
        data = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'requests': {model: 0 for model in self.models},
            'total': 0,
            'limit': self.max_requests
        }
        self.save_budget(data)
        return data

    def set_limit(self, new_limit: int) -> None:
        """Update the daily request budget limit and persist it.

        Args:
            new_limit: Maximum requests allowed per day.
        """
        if new_limit <= 0:
            raise ValueError("Budget limit must be a positive integer")
        self.max_requests = new_limit
        # Update persisted budget; do not reset usage immediately
        self.budget['limit'] = new_limit
        self.save_budget()
    
    def save_budget(self, data: Optional[dict] = None):
        """Save budget to file."""
        if data is None:
            data = self.budget
        with open('request_budget.json', 'w') as f:
            json.dump(data, f, indent=2)
    
    def get_next_model(self) -> Optional[str]:
        """
        Get next available model in round-robin fashion.
        
        Returns:
            Model identifier or None if all models are rate limited
        """
        current_time = time.time()
        checked = 0
        chosen = None
        next_available_in = None
        total = len(self.models)
        
        while checked < total:
            model = self.models[self.current_index]
            self.current_index = (self.current_index + 1) % total
            checked += 1
            
            # Hard rate limit backoff window
            if model in self.rate_limited:
                if current_time < self.rate_limited[model]:
                    remaining = self.rate_limited[model] - current_time
                    next_available_in = min(next_available_in, remaining) if next_available_in is not None else remaining
                    continue
                else:
                    del self.rate_limited[model]
            
            # Soft per-model pacing (20 req/min)
            last_ts = self.last_request_time.get(model, 0.0)
            delta = current_time - last_ts
            if delta < self.min_interval:
                remaining = self.min_interval - delta
                next_available_in = min(next_available_in, remaining) if next_available_in is not None else remaining
                continue
            
            chosen = model
            break
        
        if chosen is None:
            # No model ready yet; brief wait based on soonest availability
            if next_available_in is not None and next_available_in > 0:
                sleep_s = min(max(next_available_in, 0.05), 1.0)
                time.sleep(sleep_s)
            return None
        
        return chosen
    
    def mark_rate_limited(self, model: str, duration: int = None):
        """
        Mark a model as rate limited.
        
        Args:
            model: Model identifier
            duration: Duration in seconds (default 5 minutes)
        """
        # Default cooldown derived from 20 req/min cadence
        if duration is None:
            duration = max(1, int(self.min_interval))
        self.rate_limited[model] = time.time() + duration
        print(f"⚠️  Rate limited on {model.split('/')[-1]}, cooling down ~{duration}s")
    
    def increment_request(self, model: str):
        """
        Track a successful request and persist to file.
        
        Args:
            model: Model identifier that handled the request
        """
        self.budget['requests'][model] = self.budget['requests'].get(model, 0) + 1
        self.budget['total'] += 1
        self.last_request_time[model] = time.time()
        
        # Warn at thresholds
        percentage = (self.budget['total'] / self.max_requests) * 100
        if percentage >= 90 and self.budget['total'] % 10 == 0:
            print(f"🚨 Budget critical: {percentage:.0f}% used ({self.budget['total']}/{self.max_requests})")
        elif percentage >= 80 and self.budget['total'] % 50 == 0:
            print(f"⚠️  Budget warning: {percentage:.0f}% used ({self.budget['total']}/{self.max_requests})")
        
        self.save_budget()
    
    def check_budget(self) -> int:
        """
        Check remaining request budget.
        
        Returns:
            Number of requests remaining
        """
        return max(0, self.max_requests - self.budget['total'])
    
    def get_stats(self) -> str:
        """
        Get formatted budget statistics.
        
        Returns:
            Formatted string with budget stats
        """
        total = self.budget['total']
        limit = self.max_requests
        percentage = (total / limit) * 100 if limit > 0 else 0
        return f"{total}/{limit} requests ({percentage:.1f}%)"
    
    def get_detailed_stats(self) -> str:
        """
        Get detailed statistics per model.
        
        Returns:
            Formatted string with per-model stats
        """
        stats = [f"Total: {self.get_stats()}"]
        for model in self.models:
            count = self.budget['requests'].get(model, 0)
            model_name = model.split('/')[-1]
            stats.append(f"  {model_name}: {count} requests")
        return "\n".join(stats)

