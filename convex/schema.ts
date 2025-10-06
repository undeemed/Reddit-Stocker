import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

/**
 * Convex Schema for StockReddit
 * 
 * Stores stock analyses with AI-generated insights,
 * enabling real-time updates and re-evaluation capabilities.
 */

export default defineSchema({
  // Stock analyses with AI insights
  stockAnalyses: defineTable({
    ticker: v.string(),
    timeframe: v.string(), // "day", "week", "month"
    
    // Mention data
    totalMentions: v.number(),
    subredditMentions: v.array(v.object({
      subreddit: v.string(),
      count: v.number(),
    })),
    
    // Sentiment data
    averageSentiment: v.number(),
    sentimentBreakdown: v.object({
      positive: v.number(),
      neutral: v.number(),
      negative: v.number(),
    }),
    // Weighted sentiment score (uses counts and mentions)
    sentimentScore: v.number(),
    
    // AI-generated insights
    aiSummary: v.optional(v.string()),
    aiContext: v.optional(v.string()),
    
    // Metadata
    analyzedAt: v.number(), // Unix timestamp
    lastUpdated: v.number(),
    analysisVersion: v.number(), // Increment on re-evaluation
    
    // Raw data for re-evaluation
    rawPosts: v.optional(v.array(v.object({
      postId: v.string(),
      subreddit: v.string(),
      title: v.string(),
      text: v.string(),
      score: v.number(),
      sentiment: v.number(),
      llmContext: v.optional(v.string()),
    }))),
  })
    .index("by_ticker", ["ticker"])
    .index("by_ticker_timeframe", ["ticker", "timeframe"])
    .index("by_timeframe_updated", ["timeframe", "lastUpdated"]),
  
  // Historical snapshots for trend analysis
  stockHistory: defineTable({
    ticker: v.string(),
    timeframe: v.string(),
    mentions: v.number(),
    sentiment: v.number(),
    timestamp: v.number(),
  })
    .index("by_ticker", ["ticker"])
    .index("by_ticker_timestamp", ["ticker", "timestamp"]),
  
  // Re-evaluation queue
  revaluationQueue: defineTable({
    ticker: v.string(),
    requestedAt: v.number(),
    status: v.string(), // "pending", "processing", "completed", "failed"
    completedAt: v.optional(v.number()),
    error: v.optional(v.string()),
  })
    .index("by_status", ["status"])
    .index("by_ticker_status", ["ticker", "status"]),
});

