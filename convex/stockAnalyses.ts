import { v } from "convex/values";
import { mutation, query } from "./_generated/server";

/**
 * Store or update a stock analysis
 */
export const upsertAnalysis = mutation({
  args: {
    ticker: v.string(),
    timeframe: v.string(),
    totalMentions: v.number(),
    subredditMentions: v.array(v.object({
      subreddit: v.string(),
      count: v.number(),
    })),
    averageSentiment: v.number(),
    sentimentBreakdown: v.object({
      positive: v.number(),
      neutral: v.number(),
      negative: v.number(),
    }),
    aiSummary: v.optional(v.string()),
    aiContext: v.optional(v.string()),
    rawPosts: v.optional(v.array(v.object({
      postId: v.string(),
      subreddit: v.string(),
      title: v.string(),
      text: v.string(),
      score: v.number(),
      sentiment: v.number(),
      llmContext: v.optional(v.string()),
    }))),
  },
  handler: async (ctx, args) => {
    const now = Date.now();
    const total = args.sentimentBreakdown.positive + args.sentimentBreakdown.neutral + args.sentimentBreakdown.negative;
    // Compute weighted sentiment score: emphasize direction and confidence, scale by mention volume
    // score = (pos - neg) / max(1,total) * log1p(totalMentions)
    const base = (args.sentimentBreakdown.positive - args.sentimentBreakdown.negative) / Math.max(1, total);
    const weight = Math.log1p(args.totalMentions);
    const sentimentScore = base * weight;
    
    // Check if analysis exists
    const existing = await ctx.db
      .query("stockAnalyses")
      .withIndex("by_ticker_timeframe", (q) => 
        q.eq("ticker", args.ticker).eq("timeframe", args.timeframe)
      )
      .order("desc")
      .first();
    
    if (existing) {
      // Update existing analysis
      await ctx.db.patch(existing._id, {
        totalMentions: args.totalMentions,
        subredditMentions: args.subredditMentions,
        averageSentiment: args.averageSentiment,
        sentimentBreakdown: args.sentimentBreakdown,
        sentimentScore,
        aiSummary: args.aiSummary,
        aiContext: args.aiContext,
        rawPosts: args.rawPosts,
        lastUpdated: now,
        analysisVersion: (existing.analysisVersion || 1) + 1,
      });
      
      // Archive to history
      await ctx.db.insert("stockHistory", {
        ticker: args.ticker,
        timeframe: args.timeframe,
        mentions: args.totalMentions,
        sentiment: args.averageSentiment,
        timestamp: now,
      });
      
      return { _id: existing._id, updated: true };
    } else {
      // Create new analysis
      const id = await ctx.db.insert("stockAnalyses", {
        ticker: args.ticker,
        timeframe: args.timeframe,
        totalMentions: args.totalMentions,
        subredditMentions: args.subredditMentions,
        averageSentiment: args.averageSentiment,
        sentimentBreakdown: args.sentimentBreakdown,
        sentimentScore,
        aiSummary: args.aiSummary,
        aiContext: args.aiContext,
        rawPosts: args.rawPosts,
        analyzedAt: now,
        lastUpdated: now,
        analysisVersion: 1,
      });
      
      return { _id: id, updated: false };
    }
  },
});

/**
 * Get analysis for a specific ticker
 */
export const getAnalysis = query({
  args: {
    ticker: v.string(),
    timeframe: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    if (args.timeframe) {
      return await ctx.db
        .query("stockAnalyses")
        .withIndex("by_ticker_timeframe", (q) => 
          q.eq("ticker", args.ticker).eq("timeframe", args.timeframe as string)
        )
        .order("desc")
        .first();
    } else {
      return await ctx.db
        .query("stockAnalyses")
        .withIndex("by_ticker", (q) => q.eq("ticker", args.ticker))
        .order("desc")
        .first();
    }
  },
});

/**
 * Get all analyses for a timeframe
 */
export const listAnalyses = query({
  args: {
    timeframe: v.optional(v.string()),
    limit: v.optional(v.number()),
  },
  handler: async (ctx, args) => {
    if (args.timeframe) {
      // Use index to order by most recently updated within timeframe
      const results = await ctx.db
        .query("stockAnalyses")
        .withIndex("by_timeframe_updated", (q) => q.eq("timeframe", args.timeframe!))
        .order("desc")
        .take(args.limit ?? 50);
      return results;
    } else {
      // Get all analyses and sort by lastUpdated descending
      const results = await ctx.db
        .query("stockAnalyses")
        .collect();
      return results
        .sort((a, b) => (b.lastUpdated ?? 0) - (a.lastUpdated ?? 0))
        .slice(0, args.limit ?? 50);
    }
  },
});

/**
 * Get top stocks by mentions
 */
export const getTopStocks = query({
  args: {
    timeframe: v.optional(v.string()),
    limit: v.optional(v.number()),
  },
  handler: async (ctx, args) => {
    let analyses;
    
    if (args.timeframe) {
      // Filter by timeframe
      analyses = await ctx.db
        .query("stockAnalyses")
        .filter((q) => q.eq(q.field("timeframe"), args.timeframe))
        .order("desc")
        .take(100);
    } else {
      // Get all analyses
      analyses = await ctx.db
        .query("stockAnalyses")
        .order("desc")
        .take(100);
    }
    
    // Sort by mentions and limit
    return analyses
      .sort((a, b) => b.totalMentions - a.totalMentions)
      .slice(0, args.limit ?? 10);
  },
});

/**
 * Get historical data for a ticker
 */
export const getHistory = query({
  args: {
    ticker: v.string(),
    limit: v.optional(v.number()),
  },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("stockHistory")
      .withIndex("by_ticker", (q) => q.eq("ticker", args.ticker))
      .order("desc")
      .take(args.limit || 100);
  },
});

/**
 * Delete an analysis
 */
export const deleteAnalysis = mutation({
  args: {
    ticker: v.string(),
    timeframe: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    if (args.timeframe) {
      const analysis = await ctx.db
        .query("stockAnalyses")
        .withIndex("by_ticker_timeframe", (q) => 
          q.eq("ticker", args.ticker).eq("timeframe", args.timeframe as string)
        )
        .first();
      
      if (analysis) {
        await ctx.db.delete(analysis._id);
        return { deleted: true };
      }
    } else {
      // Delete all analyses for ticker
      const analyses = await ctx.db
        .query("stockAnalyses")
        .withIndex("by_ticker", (q) => q.eq("ticker", args.ticker))
        .collect();
      
      for (const analysis of analyses) {
        await ctx.db.delete(analysis._id);
      }
      
      return { deleted: analyses.length };
    }
    
    return { deleted: 0 };
  },
});

/**
 * Queue a ticker for re-evaluation
 */
export const queueRevaluation = mutation({
  args: {
    ticker: v.string(),
  },
  handler: async (ctx, args) => {
    const id = await ctx.db.insert("revaluationQueue", {
      ticker: args.ticker,
      requestedAt: Date.now(),
      status: "pending",
    });
    
    return { _id: id };
  },
});

/**
 * Get pending re-evaluations
 */
export const getPendingRevaluations = query({
  args: {},
  handler: async (ctx) => {
    return await ctx.db
      .query("revaluationQueue")
      .withIndex("by_status", (q) => q.eq("status", "pending"))
      .order("asc")
      .collect();
  },
});

/**
 * Update re-evaluation status
 */
export const updateRevaluationStatus = mutation({
  args: {
    id: v.id("revaluationQueue"),
    status: v.string(),
    error: v.optional(v.string()),
  },
  handler: async (ctx, args) => {
    const update: any = {
      status: args.status,
    };
    
    if (args.status === "completed" || args.status === "failed") {
      update.completedAt = Date.now();
    }
    
    if (args.error) {
      update.error = args.error;
    }
    
    await ctx.db.patch(args.id, update);
  },
});

