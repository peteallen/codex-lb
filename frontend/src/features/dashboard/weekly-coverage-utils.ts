import type { WeeklyCoverage, WeeklyCoverageInterval } from "@/features/dashboard/schemas";

export const WEEKLY_COVERAGE_DEFAULT_DAYS = 7;
export const WEEKLY_COVERAGE_MAX_DAYS = 14;

const DAY_MS = 24 * 60 * 60 * 1000;

export type CoverageTimelineSegment = WeeklyCoverageInterval & {
  startMs: number;
  endMs: number;
  leftPercent: number;
  widthPercent: number;
};

export type CoverageDurationParts = {
  days: number;
  hours: number;
  minutes: number;
};

function parseTime(value: string): number | null {
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function getCoverageWindow(
  coverage: WeeklyCoverage,
  days: number,
): { startMs: number; endMs: number } | null {
  const startMs = parseTime(coverage.generatedAt);
  const horizonMs = parseTime(coverage.horizonAt);
  if (startMs === null || horizonMs === null || horizonMs <= startMs) {
    return null;
  }

  const requestedEndMs = startMs + Math.min(days, WEEKLY_COVERAGE_MAX_DAYS) * DAY_MS;
  return {
    startMs,
    endMs: Math.min(requestedEndMs, horizonMs),
  };
}

export function getCoverageTimelineSegments(
  intervals: WeeklyCoverageInterval[],
  window: { startMs: number; endMs: number } | null,
): CoverageTimelineSegment[] {
  if (!window || window.endMs <= window.startMs) {
    return [];
  }

  const durationMs = window.endMs - window.startMs;
  return intervals
    .map((interval) => {
      const intervalStartMs = parseTime(interval.startAt);
      const intervalEndMs = parseTime(interval.endAt);
      if (intervalStartMs === null || intervalEndMs === null || intervalEndMs <= intervalStartMs) {
        return null;
      }

      const startMs = Math.max(window.startMs, intervalStartMs);
      const endMs = Math.min(window.endMs, intervalEndMs);
      if (endMs <= startMs) {
        return null;
      }

      return {
        ...interval,
        startMs,
        endMs,
        leftPercent: ((startMs - window.startMs) / durationMs) * 100,
        widthPercent: ((endMs - startMs) / durationMs) * 100,
      };
    })
    .filter((segment): segment is CoverageTimelineSegment => segment !== null)
    .sort((left, right) => left.startMs - right.startMs);
}

export function findFirstCoverageGap(coverage: WeeklyCoverage): CoverageTimelineSegment | null {
  const window = getCoverageWindow(coverage, WEEKLY_COVERAGE_MAX_DAYS);
  if (!window) {
    return null;
  }

  return getCoverageTimelineSegments(coverage.intervals, window).find(
    (interval) => interval.state === "exhausted",
  ) ?? null;
}

export function isGapOutsideDefaultWindow(coverage: WeeklyCoverage): boolean {
  const gap = findFirstCoverageGap(coverage);
  const window = getCoverageWindow(coverage, WEEKLY_COVERAGE_DEFAULT_DAYS);
  if (!gap || !window) {
    return false;
  }

  return gap.startMs >= window.endMs;
}

export function getCoverageHorizonDays(coverage: WeeklyCoverage): number {
  const window = getCoverageWindow(coverage, WEEKLY_COVERAGE_MAX_DAYS);
  if (!window) {
    return WEEKLY_COVERAGE_MAX_DAYS;
  }
  return Math.max(1, Math.round((window.endMs - window.startMs) / DAY_MS));
}

export function getCoverageDurationParts(milliseconds: number): CoverageDurationParts {
  const totalMinutes = Math.max(1, Math.ceil(milliseconds / 60_000));
  const days = Math.floor(totalMinutes / (24 * 60));
  const hours = Math.floor((totalMinutes % (24 * 60)) / 60);
  const minutes = totalMinutes % 60;
  return { days, hours, minutes };
}
