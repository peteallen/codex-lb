import { describe, expect, it } from "vitest";

import { HourlyReportRowSchema, ReportsResponseSchema } from "./schemas";

describe("ReportsResponseSchema", () => {
  it("parses totalConversations on summary and conversations on daily rows", () => {
    const parsed = ReportsResponseSchema.parse({
      summary: {
        totalCostUsd: 12.5, totalInputTokens: 300, totalOutputTokens: 200,
        totalCachedTokens: 0, totalRequests: 25, totalErrors: 1,
        totalConversations: 7, activeAccounts: 3,
        avgCostPerDay: 4.17, avgRequestsPerDay: 8.33,
      },
      comparison: { canCompare: true, previous: { totalCostUsd: 10, totalTokens: 400, totalRequests: 20 } },
      chartGranularity: "hour",
      hourly: [{ hour: "2026-06-05T12:00:00-07:00", requests: 2, inputTokens: 20, outputTokens: 10, cachedInputTokens: 5, costUsd: 0.5, activeAccounts: 1, errorCount: 0 }],
      daily: [{ date: "2026-06-05", requests: 10, conversations: 3, inputTokens: 100, outputTokens: 50, cachedInputTokens: 0, costUsd: 1, activeAccounts: 2, errorCount: 0 }],
      byModel: [{ model: "gpt-5.1", costUsd: 12.5, requests: 25, percentage: 100 }],
      byUseragent: [{ useragent: "claude-code", costUsd: 12.5, requests: 25, percentage: 100 }],
      byAccount: [],
    });
    expect(parsed.summary.totalConversations).toBe(7);
    expect(parsed.daily[0]?.conversations).toBe(3);
    expect(parsed.hourly[0]?.hour).toBe("2026-06-05T12:00:00-07:00");
  });

  it("requires hourly bucket timestamps to include a timezone offset", () => {
    expect(() =>
      HourlyReportRowSchema.parse({
        hour: "2026-06-05T12:00:00",
        requests: 0,
        inputTokens: 0,
        outputTokens: 0,
        cachedInputTokens: 0,
        costUsd: 0,
        activeAccounts: 0,
        errorCount: 0,
      }),
    ).toThrow();
  });

  it("rejects omitted totalConversations on summary", () => {
    expect(() =>
      ReportsResponseSchema.parse({
        summary: {
          totalCostUsd: 12.5, totalInputTokens: 300, totalOutputTokens: 200,
          totalCachedTokens: 0, totalRequests: 25, totalErrors: 1,
          activeAccounts: 3, avgCostPerDay: 4.17, avgRequestsPerDay: 8.33,
        },
        comparison: { canCompare: true, previous: { totalCostUsd: 10, totalTokens: 400, totalRequests: 20 } },
        chartGranularity: "day",
        hourly: [],
        daily: [{ date: "2026-06-05", requests: 10, conversations: 0, inputTokens: 100, outputTokens: 50, cachedInputTokens: 0, costUsd: 1, activeAccounts: 2, errorCount: 0 }],
        byModel: [{ model: "gpt-5.1", costUsd: 12.5, requests: 25, percentage: 100 }],
        byUseragent: [{ useragent: "claude-code", costUsd: 12.5, requests: 25, percentage: 100 }],
        byAccount: [],
      }),
    ).toThrow();
  });


  it("parses the required comparison block", () => {
    const parsed = ReportsResponseSchema.parse({
      summary: {
        totalCostUsd: 12.5,
        totalInputTokens: 300,
        totalOutputTokens: 200,
        totalCachedTokens: 0,
        totalRequests: 25,
        totalErrors: 1,
        totalConversations: 0,
        activeAccounts: 3,
        avgCostPerDay: 4.17,
        avgRequestsPerDay: 8.33,
      },
      comparison: {
        canCompare: true,
        previous: {
          totalCostUsd: 10,
          totalTokens: 400,
          totalRequests: 20,
        },
      },
      chartGranularity: "day",
      hourly: [],
      daily: [],
      byModel: [
        {
          model: "gpt-5.1",
          costUsd: 12.5,
          requests: 25,
          percentage: 100,
        },
      ],
      byUseragent: [
        {
          useragent: "claude-code",
          costUsd: 12.5,
          requests: 25,
          percentage: 100,
        },
      ],
      byAccount: [],
    });

    expect(parsed.comparison.canCompare).toBe(true);
    expect(parsed.comparison.previous.totalCostUsd).toBe(10);
    expect(parsed.comparison.previous.totalTokens).toBe(400);
    expect(parsed.comparison.previous.totalRequests).toBe(20);
    expect(parsed.byModel[0]?.requests).toBe(25);
    expect(parsed.byUseragent[0]?.useragent).toBe("claude-code");
  });

  it("rejects payloads without the comparison block", () => {
    expect(() =>
      ReportsResponseSchema.parse({
        summary: {
          totalCostUsd: 12.5,
          totalInputTokens: 300,
          totalOutputTokens: 200,
          totalCachedTokens: 0,
          totalRequests: 25,
          totalErrors: 1,
          activeAccounts: 3,
          avgCostPerDay: 4.17,
          avgRequestsPerDay: 8.33,
        },
        daily: [],
        byModel: [],
        byUseragent: [],
        byAccount: [],
      }),
    ).toThrow(/comparison/i);
  });

  it("rejects comparison blocks without previous totals", () => {
    expect(() =>
      ReportsResponseSchema.parse({
        summary: {
          totalCostUsd: 12.5,
          totalInputTokens: 300,
          totalOutputTokens: 200,
          totalCachedTokens: 0,
          totalRequests: 25,
          totalErrors: 1,
          activeAccounts: 3,
          avgCostPerDay: 4.17,
          avgRequestsPerDay: 8.33,
        },
        comparison: {
          canCompare: false,
        },
        daily: [],
        byModel: [],
        byUseragent: [],
        byAccount: [],
      }),
    ).toThrow(/previous/i);
  });

  it("rejects byModel entries without request totals", () => {
    expect(() =>
      ReportsResponseSchema.parse({
        summary: {
          totalCostUsd: 12.5,
          totalInputTokens: 300,
          totalOutputTokens: 200,
          totalCachedTokens: 0,
          totalRequests: 25,
          totalErrors: 1,
          activeAccounts: 3,
          avgCostPerDay: 4.17,
          avgRequestsPerDay: 8.33,
        },
        comparison: {
          canCompare: true,
          previous: {
            totalCostUsd: 10,
            totalTokens: 400,
            totalRequests: 20,
          },
        },
        chartGranularity: "day",
        hourly: [],
        daily: [],
        byModel: [
          {
            model: "gpt-5.1",
            costUsd: 12.5,
            percentage: 100,
          },
        ],
        byUseragent: [],
        byAccount: [],
      }),
    ).toThrow(/requests/i);
  });

  it("rejects payloads without useragent breakdowns", () => {
    expect(() =>
      ReportsResponseSchema.parse({
        summary: {
          totalCostUsd: 12.5,
          totalInputTokens: 300,
          totalOutputTokens: 200,
          totalCachedTokens: 0,
          totalRequests: 25,
          totalErrors: 1,
          activeAccounts: 3,
          avgCostPerDay: 4.17,
          avgRequestsPerDay: 8.33,
        },
        comparison: {
          canCompare: true,
          previous: {
            totalCostUsd: 10,
            totalTokens: 400,
            totalRequests: 20,
          },
        },
        chartGranularity: "day",
        hourly: [],
        daily: [],
        byModel: [
          {
            model: "gpt-5.1",
            costUsd: 12.5,
            requests: 25,
            percentage: 100,
          },
        ],
        byAccount: [],
      }),
    ).toThrow(/byUseragent/i);
  });
});
