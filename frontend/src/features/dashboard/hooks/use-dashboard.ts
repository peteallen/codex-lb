import { useQuery } from "@tanstack/react-query";

import { getDashboardOverview, getDashboardProjections } from "@/features/dashboard/api";
import {
  DEFAULT_OVERVIEW_TIMEFRAME,
  type DashboardOverviewRange,
  type OverviewTimeframe,
} from "@/features/dashboard/schemas";

export function useDashboard(
  range: DashboardOverviewRange | OverviewTimeframe = DEFAULT_OVERVIEW_TIMEFRAME,
) {
  const overviewRange: DashboardOverviewRange =
    typeof range === "string" ? { mode: "preset", timeframe: range } : range;
  const queryRange = overviewRange.mode === "preset" ? overviewRange.timeframe : overviewRange;
  return useQuery({
    queryKey: ["dashboard", "overview", queryRange],
    queryFn: () => getDashboardOverview({ range: overviewRange }),
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
  });
}

export function useDashboardProjections(enabled = true) {
  return useQuery({
    queryKey: ["dashboard", "projections"],
    queryFn: getDashboardProjections,
    enabled,
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
  });
}
