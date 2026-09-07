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

export type TimeToFirstTokenChartProps = {
  startDate: string;
  endDate: string;
  data: DailyReportRow[];
  hourly: HourlyReportRow[];
  chartGranularity: ReportChartGranularity;
};

function formatSeconds(value: number): string {
  return `${(value / 1000).toFixed(1)}s`;
}

export function TimeToFirstTokenChart({
  startDate,
  endDate,
  data,
  hourly,
  chartGranularity,
}: TimeToFirstTokenChartProps) {
  const { t } = useTranslation();
  const chartData = buildReportChartRows(startDate, endDate, chartGranularity, data, hourly).map((d) => ({
    date: d.date,
    ttft: d.medianTtftMs,
  }));

  return (
    <div className="rounded-xl border bg-card p-5">
      <div className="text-sm font-semibold text-foreground">{t("reports.charts.timeToFirstToken")}</div>
      <div className="mt-4 h-[200px]">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData} margin={{ top: 5, right: 10, left: 10, bottom: 0 }}>
            <defs>
              <linearGradient id="ttftGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#f97316" stopOpacity={0.3} />
                <stop offset="100%" stopColor="#f97316" stopOpacity={0.05} />
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
              tickFormatter={formatSeconds}
            />
            <Tooltip
              content={
                <ChartTooltip
                  names={{ ttft: t("reports.charts.medianTtft") }}
                  formatLabel={
                    chartGranularity === "hour" ? formatReportBucketTooltip : undefined
                  }
                  formatValue={formatSeconds}
                />
              }
            />
            <Area
              type="monotone"
              dataKey="ttft"
              stroke="#f97316"
              strokeWidth={2}
              fill="url(#ttftGrad)"
              dot={false}
              activeDot={{ r: 4, strokeWidth: 1.5, fill: "hsl(var(--popover))" }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
