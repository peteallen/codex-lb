import type {
  DailyReportRow,
  HourlyReportRow,
  ReportChartGranularity,
} from "./schemas";

export type ReportChartRow = {
  date: string;
  requests: number;
  inputTokens: number;
  outputTokens: number;
  cachedInputTokens: number;
  costUsd: number;
  activeAccounts: number;
  errorCount: number;
  medianTtftMs: number;
  medianTps: number;
  medianQueueMs: number;
};

const REPORT_HOUR_PATTERN =
  /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::\d{2}(?:\.\d+)?)?(Z|[+-]\d{2}:\d{2})$/;

export function buildContinuousDailyRows(
  startDate: string,
  endDate: string,
  rows: DailyReportRow[],
): DailyReportRow[] {
  if (!isISODate(startDate) || !isISODate(endDate) || startDate > endDate) {
    return rows;
  }

  const rowsByDate = new Map(rows.map((row) => [row.date, row]));
  const continuousRows: DailyReportRow[] = [];

  for (let current = startDate; current <= endDate; current = nextISODate(current)) {
    continuousRows.push(rowsByDate.get(current) ?? createZeroRow(current));
  }

  return continuousRows;
}

export function buildReportChartRows(
  startDate: string,
  endDate: string,
  chartGranularity: ReportChartGranularity,
  dailyRows: DailyReportRow[],
  hourlyRows: HourlyReportRow[],
): ReportChartRow[] {
  if (chartGranularity === "hour") {
    return hourlyRows.map((row) => toReportChartRow(row, row.hour));
  }

  return buildContinuousDailyRows(startDate, endDate, dailyRows).map((row) =>
    toReportChartRow(row, row.date.slice(5)),
  );
}

export function formatReportBucketHour(value: string): string {
  const match = REPORT_HOUR_PATTERN.exec(value);
  if (!match) {
    return value;
  }

  return `${match[2]}-${match[3]} ${match[4]}:${match[5]}`;
}

export function formatReportBucketTooltip(value: string): string {
  const match = REPORT_HOUR_PATTERN.exec(value);
  if (!match) {
    return value;
  }
  const offset = match[6] === "Z" ? "+00:00" : match[6];
  return `${match[2]}-${match[3]} ${match[4]}:${match[5]} UTC${offset}`;
}

function nextISODate(date: string): string {
  const nextDate = new Date(`${date}T00:00:00Z`);
  nextDate.setUTCDate(nextDate.getUTCDate() + 1);
  return nextDate.toISOString().slice(0, 10);
}

function isISODate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return false;
  }

  const parsed = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}

function createZeroRow(date: string): DailyReportRow {
  return {
    date,
    requests: 0,
    conversations: 0,
    inputTokens: 0,
    outputTokens: 0,
    cachedInputTokens: 0,
    costUsd: 0,
    activeAccounts: 0,
    errorCount: 0,
    medianTtftMs: 0,
    medianTps: 0,
    medianQueueMs: 0,
  };
}

function toReportChartRow(
  row: DailyReportRow | HourlyReportRow,
  date: string,
): ReportChartRow {
  return {
    date,
    requests: row.requests,
    inputTokens: row.inputTokens,
    outputTokens: row.outputTokens,
    cachedInputTokens: row.cachedInputTokens,
    costUsd: row.costUsd,
    activeAccounts: row.activeAccounts,
    errorCount: row.errorCount,
    medianTtftMs: row.medianTtftMs ?? 0,
    medianTps: row.medianTps ?? 0,
    medianQueueMs: row.medianQueueMs ?? 0,
  };
}
