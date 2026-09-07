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

export type QueueWaitChartProps = {
  startDate: string;
  endDate: string;
  data: DailyReportRow[];
  hourly: HourlyReportRow[];
  chartGranularity: ReportChartGranularity;
};

function formatQueueMs(value: number): string {
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1)}s`;
  }
  return `${Math.round(value)}ms`;
}

export function QueueWaitChart({
  startDate,
  endDate,
  data,
  hourly,
  chartGranularity,
}: QueueWaitChartProps) {
  const { t } = useTranslation();
  const chartData = buildReportChartRows(startDate, endDate, chartGranularity, data, hourly).map((d) => ({
    date: d.date,
    queue: d.medianQueueMs,
  }));

  return (
    <div className="rounded-xl border bg-card p-5">
      <div className="text-sm font-semibold text-foreground">{t("reports.charts.queueWait")}</div>
      <div className="mt-4 h-[200px]">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData} margin={{ top: 5, right: 10, left: 10, bottom: 0 }}>
            <defs>
              <linearGradient id="queueGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.3} />
                <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0.05} />
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
              tickFormatter={formatQueueMs}
            />
            <Tooltip
              content={
                <ChartTooltip
                  names={{ queue: t("reports.charts.medianQueueWait") }}
                  formatLabel={
                    chartGranularity === "hour" ? formatReportBucketTooltip : undefined
                  }
                  formatValue={formatQueueMs}
                />
              }
            />
            <Area
              type="monotone"
              dataKey="queue"
              stroke="#8b5cf6"
              strokeWidth={2}
              fill="url(#queueGrad)"
              dot={false}
              activeDot={{ r: 4, strokeWidth: 1.5, fill: "hsl(var(--popover))" }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
