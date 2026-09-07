import { useTranslation } from "react-i18next";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "@/components/lazy-recharts";
import type {
  DailyReportRow,
  HourlyReportRow,
  ReportChartGranularity,
} from "../schemas";
import {
  buildReportChartRows,
  formatReportBucketHour,
  formatReportBucketTooltip,
} from "../daily-series";
import { ChartTooltip } from "./chart-tooltip";

export type TokensPerDayChartProps = {
  startDate: string;
  endDate: string;
  data: DailyReportRow[];
  hourly: HourlyReportRow[];
  chartGranularity: ReportChartGranularity;
};

function formatTokens(v: number): string {
  if (v >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(1)}B`;
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(0)}K`;
  return String(v);
}

export function TokensPerDayChart({
  startDate,
  endDate,
  data,
  hourly,
  chartGranularity,
}: TokensPerDayChartProps) {
  const { t } = useTranslation();
  const chartData = buildReportChartRows(startDate, endDate, chartGranularity, data, hourly).map((d) => ({
    date: d.date,
    input: d.inputTokens,
    output: d.outputTokens,
  }));

  return (
    <div className="rounded-xl border bg-card p-5">
      <div className="text-sm font-semibold text-foreground">
        {t(
          chartGranularity === "hour"
            ? "reports.charts.tokensByHour"
            : "reports.charts.tokensByDay",
        )}
      </div>
      <div className="mt-4 h-[200px]">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData} margin={{ top: 5, right: 10, left: 10, bottom: 0 }}>
            <defs>
              <linearGradient id="inputGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.3} />
                <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0.05} />
              </linearGradient>
              <linearGradient id="outputGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#ec4899" stopOpacity={0.3} />
                <stop offset="100%" stopColor="#ec4899" stopOpacity={0.05} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
            <XAxis
              dataKey="date"
              tickFormatter={formatReportBucketHour}
              tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
              axisLine={false}
              tickLine={false}
              tickFormatter={formatTokens}
            />
            <Tooltip
              content={
                <ChartTooltip
                  names={{ input: t("reports.charts.input"), output: t("reports.charts.output") }}
                  formatLabel={
                    chartGranularity === "hour" ? formatReportBucketTooltip : undefined
                  }
                  formatValue={(v) => formatTokens(v)}
                />
              }
            />
            <Area
              type="monotone"
              dataKey="input"
              stroke="#8b5cf6"
              strokeWidth={2}
              fill="url(#inputGrad)"
              dot={false}
              activeDot={{ r: 4, strokeWidth: 1.5, fill: "hsl(var(--popover))" }}
            />
            <Area
              type="monotone"
              dataKey="output"
              stroke="#ec4899"
              strokeWidth={2}
              fill="url(#outputGrad)"
              dot={false}
              activeDot={{ r: 4, strokeWidth: 1.5, fill: "hsl(var(--popover))" }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
