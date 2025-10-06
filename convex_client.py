"""
Convex Database Client for StockReddit

Provides a Python interface to store, retrieve, and manage stock analyses
in Convex's real-time cloud database.
"""
import os
from typing import Optional, List, Dict, Any
from convex import ConvexClient
from dotenv import load_dotenv

load_dotenv()


class StockConvexClient:
    """Client for interacting with Convex database."""
    
    def __init__(self, url: Optional[str] = None):
        """
        Initialize Convex client.
        
        Args:
            url: Convex deployment URL (defaults to CONVEX_URL env var)
        """
        self.url = url or os.getenv("CONVEX_URL")
        if not self.url:
            raise ValueError(
                "CONVEX_URL not found. Set it in .env or pass as parameter.\n"
                "Get your URL by running: npx convex dev"
            )
        
        self.client = ConvexClient(self.url)
    
    def save_analysis(
        self,
        ticker: str,
        timeframe: str,
        total_mentions: int,
        subreddit_mentions: List[Dict[str, Any]],
        average_sentiment: float,
        sentiment_breakdown: Dict[str, int],
        ai_summary: Optional[str] = None,
        ai_context: Optional[str] = None,
        raw_posts: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Save or update a stock analysis in Convex.
        
        Args:
            ticker: Stock ticker symbol
            timeframe: Analysis timeframe (day, week, month)
            total_mentions: Total mentions across all subreddits
            subreddit_mentions: List of {subreddit, count} dicts
            average_sentiment: Average sentiment score
            sentiment_breakdown: {positive, neutral, negative} counts
            ai_summary: Optional AI-generated summary
            ai_context: Optional AI context insights
            raw_posts: Optional raw post data for re-evaluation
            
        Returns:
            Dictionary with _id and updated status
        """
        # Build args, only include optional fields if they're not None
        args = {
            "ticker": ticker,
            "timeframe": timeframe,
            "totalMentions": total_mentions,
            "subredditMentions": subreddit_mentions,
            "averageSentiment": average_sentiment,
            "sentimentBreakdown": sentiment_breakdown,
        }
        
        if ai_summary is not None:
            args["aiSummary"] = ai_summary
        if ai_context is not None:
            args["aiContext"] = ai_context
        if raw_posts is not None:
            args["rawPosts"] = raw_posts
        
        return self.client.mutation(
            "stockAnalyses:upsertAnalysis",
            args
        )
    
    def get_analysis(
        self,
        ticker: str,
        timeframe: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get analysis for a specific ticker.
        
        Args:
            ticker: Stock ticker symbol
            timeframe: Optional timeframe filter
            
        Returns:
            Analysis dictionary or None if not found
        """
        args = {"ticker": ticker}
        if timeframe is not None:
            args["timeframe"] = timeframe
        return self.client.query(
            "stockAnalyses:getAnalysis",
            args
        )
    
    def list_analyses(
        self,
        timeframe: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        List all stock analyses.
        
        Args:
            timeframe: Optional timeframe filter
            limit: Maximum number of results
            
        Returns:
            List of analysis dictionaries
        """
        args = {"limit": limit}
        if timeframe is not None:
            args["timeframe"] = timeframe
        return self.client.query(
            "stockAnalyses:listAnalyses",
            args
        )
    
    def get_top_stocks(
        self,
        timeframe: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get top stocks by mention count.
        
        Args:
            timeframe: Optional timeframe to filter by
            limit: Number of top stocks to return
            
        Returns:
            List of top stock analyses
        """
        args = {"limit": limit}
        if timeframe is not None:
            args["timeframe"] = timeframe
        return self.client.query(
            "stockAnalyses:getTopStocks",
            args
        )
    
    def get_history(
        self,
        ticker: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get historical data for a ticker.
        
        Args:
            ticker: Stock ticker symbol
            limit: Number of historical records
            
        Returns:
            List of historical snapshots
        """
        return self.client.query(
            "stockAnalyses:getHistory",
            {"ticker": ticker, "limit": limit}
        )
    
    def delete_analysis(
        self,
        ticker: str,
        timeframe: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Delete analysis for a ticker.
        
        Args:
            ticker: Stock ticker symbol
            timeframe: Optional timeframe (deletes all if not specified)
            
        Returns:
            Dictionary with deletion count
        """
        args = {"ticker": ticker}
        if timeframe is not None:
            args["timeframe"] = timeframe
        return self.client.mutation(
            "stockAnalyses:deleteAnalysis",
            args
        )
    
    def queue_revaluation(self, ticker: str) -> Dict[str, Any]:
        """
        Queue a ticker for AI re-evaluation.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Dictionary with queue entry _id
        """
        return self.client.mutation(
            "stockAnalyses:queueRevaluation",
            {"ticker": ticker}
        )
    
    def get_pending_revaluations(self) -> List[Dict[str, Any]]:
        """
        Get all pending re-evaluation requests.
        
        Returns:
            List of pending re-evaluation entries
        """
        return self.client.query(
            "stockAnalyses:getPendingRevaluations",
            {}
        )
    
    def update_revaluation_status(
        self,
        entry_id: str,
        status: str,
        error: Optional[str] = None
    ) -> None:
        """
        Update the status of a re-evaluation request.
        
        Args:
            entry_id: Re-evaluation queue entry ID
            status: New status (pending, processing, completed, failed)
            error: Optional error message
        """
        self.client.mutation(
            "stockAnalyses:updateRevaluationStatus",
            {"id": entry_id, "status": status, "error": error}
        )
    
    def subscribe_to_analysis(
        self,
        ticker: str,
        timeframe: Optional[str] = None
    ):
        """
        Subscribe to real-time updates for a ticker analysis.
        
        Args:
            ticker: Stock ticker symbol
            timeframe: Optional timeframe filter
            
        Yields:
            Updated analysis data as it changes
        """
        args = {"ticker": ticker}
        if timeframe is not None:
            args["timeframe"] = timeframe
        for analysis in self.client.subscribe(
            "stockAnalyses:getAnalysis",
            args
        ):
            yield analysis


def test_convex_connection():
    """Test Convex connection and display setup instructions if needed."""
    try:
        client = StockConvexClient()
        print("✓ Convex connection successful!")
        print(f"  Connected to: {client.url}")
        return True
    except ValueError as e:
        print("❌ Convex not configured")
        print(f"\n{e}")
        print("\nSetup instructions:")
        print("1. Run: npm install")
        print("2. Run: npx convex dev")
        print("3. Follow prompts to create deployment")
        print("4. Add CONVEX_URL to your .env file")
        return False
    except Exception as e:
        print(f"❌ Convex connection failed: {e}")
        return False


if __name__ == "__main__":
    test_convex_connection()

