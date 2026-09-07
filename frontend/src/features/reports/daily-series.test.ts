import { describe, expect, it } from "vitest";

import {
  buildReportChartRows,
  formatReportBucketHour,
  formatReportBucketTooltip,
} from "./daily-series";

describe("report chart series", () => {
  it("uses hourly rows and keeps their offset-qualified ISO labels", () => {
    const rows = buildReportChartRows(
      "2026-06-05",
      "2026-06-05",
      "hour",
      [],
      [
        {
          hour: "2026-06-05T01:00:00-07:00",
          requests: 2,
          inputTokens: 100,
          outputTokens: 40,
          cachedInputTokens: 10,
          costUsd: 0.25,
          activeAccounts: 1,
          errorCount: 0,
          medianTtftMs: 120,
          medianTps: 24,
          medianQueueMs: 30,
        },
      ],
    );

    expect(rows).toEqual([
      {
        date: "2026-06-05T01:00:00-07:00",
        requests: 2,
        inputTokens: 100,
        outputTokens: 40,
        cachedInputTokens: 10,
        costUsd: 0.25,
        activeAccounts: 1,
        errorCount: 0,
        medianTtftMs: 120,
        medianTps: 24,
        medianQueueMs: 30,
      },
    ]);
  });

  it("keeps daily gap filling when the server selects daily charts", () => {
    const rows = buildReportChartRows(
      "2026-06-05",
      "2026-06-07",
      "day",
      [
        {
          date: "2026-06-05",
          requests: 1,
          conversations: 1,
          inputTokens: 10,
          outputTokens: 5,
          cachedInputTokens: 0,
          costUsd: 0.1,
          activeAccounts: 1,
          errorCount: 0,
        },
      ],
      [],
    );

    expect(rows.map(({ date, requests }) => ({ date, requests }))).toEqual([
      { date: "06-05", requests: 1 },
      { date: "06-06", requests: 0 },
      { date: "06-07", requests: 0 },
    ]);
  });

  it("formats hourly axis labels without shifting the report timezone", () => {
    expect(formatReportBucketHour("2026-11-01T01:00:00-04:00")).toBe("11-01 01:00");
    expect(formatReportBucketHour("2026-11-01T01:00:00-05:00")).toBe("11-01 01:00");
    expect(formatReportBucketHour("06-05")).toBe("06-05");
    expect(formatReportBucketTooltip("2026-06-05T01:00:00-07:00")).toBe(
      "06-05 01:00 UTC-07:00",
    );
  });
});
