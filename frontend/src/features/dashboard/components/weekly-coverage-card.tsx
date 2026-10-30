import { useId, useState } from "react";
import { ChevronRight } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";
import type { WeeklyCoverage, WeeklyCoverageAccount, WeeklyCoverageInterval } from "@/features/dashboard/schemas";
import {
  findFirstCoverageGap,
  getCoverageDurationParts,
  getCoverageHorizonDays,
  getCoverageTimelineSegments,
  getCoverageWindow,
  isGapOutsideDefaultWindow,
} from "@/features/dashboard/weekly-coverage-utils";
import { useDateDisplayFormatStore } from "@/hooks/use-date-format";
import { formatDateTimeInline, formatSlug } from "@/utils/formatters";

export type WeeklyCoverageCardProps = { coverage: WeeklyCoverage | null };
type Translation = ReturnType<typeof useTranslation>["t"];
type DateFormat = "default" | "iso8601";
type TimelineWindow = { startMs: number; endMs: number } | null;
const WEEK_MS = 7 * 24 * 60 * 60 * 1000;
const ROW_GRID = "grid grid-cols-[minmax(0,100px)_minmax(0,1fr)] items-center gap-3 sm:grid-cols-[minmax(0,160px)_minmax(0,1fr)]";
const AVAILABLE_COLOR = "bg-blue-200 dark:bg-[#304568]";
const POOL_GAP_COLOR = "bg-[#e7cfc1] dark:bg-[#604437]";

function humanizeCode(value: string): string {
  return formatSlug(value.replaceAll("-", "_"));
}

function formatCoverageDate(iso: string, dateDisplayFormat: "default" | "iso8601"): string {
  if (dateDisplayFormat === "iso8601") return formatDateTimeInline(iso, dateDisplayFormat);
  return new Intl.DateTimeFormat(undefined, {
    month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  }).format(new Date(iso));
}

function formatDuration(
  milliseconds: number,
  t: ReturnType<typeof useTranslation>["t"],
): string {
  const { days, hours, minutes } = getCoverageDurationParts(milliseconds);
  if (days > 0) {
    return hours > 0
      ? t(
          days === 1
            ? "dashboard.weeklyCoverage.duration.oneDayHours"
            : "dashboard.weeklyCoverage.duration.daysHours",
          { days, hours },
        )
      : t(
          days === 1
            ? "dashboard.weeklyCoverage.duration.oneDay"
            : "dashboard.weeklyCoverage.duration.days",
          { count: days },
        );
  }
  if (hours > 0) {
    return minutes > 0
      ? t("dashboard.weeklyCoverage.duration.hoursMinutes", { hours, minutes })
      : t("dashboard.weeklyCoverage.duration.hours", { count: hours });
  }
  return t("dashboard.weeklyCoverage.duration.minutes", { count: minutes });
}

function formatReserveHours(
  hours: number,
  t: ReturnType<typeof useTranslation>["t"],
): string {
  if (hours <= 0) {
    return t("dashboard.weeklyCoverage.reserveZeroHours");
  }
  if (hours < 1) {
    return t("dashboard.weeklyCoverage.reserveLessThanHour");
  }
  const value = hours < 10 ? hours.toFixed(1) : Math.round(hours).toString();
  return t("dashboard.weeklyCoverage.reserveHours", { hours: value });
}

function formatCoveragePercent(value: number): string {
  const rounded = Math.round(value * 10) / 10;
  return Number.isInteger(rounded) ? rounded.toString() : rounded.toFixed(1);
}

function translatedCode(
  t: ReturnType<typeof useTranslation>["t"],
  prefix: string,
  value: string,
): string {
  return t(`${prefix}.${value}`, { defaultValue: humanizeCode(value) });
}

function accountEvidenceDetails(
  account: WeeklyCoverageAccount,
  t: ReturnType<typeof useTranslation>["t"],
): string[] {
  const details: string[] = [];
  if (account.diagnostics.discardedIntervalCount > 0) {
    details.push(t("dashboard.weeklyCoverage.evidence.discardedIntervals", {
      count: account.diagnostics.discardedIntervalCount,
    }));
  }
  if (account.diagnostics.unpricedModels.length > 0) {
    details.push(t("dashboard.weeklyCoverage.evidence.unpricedModels", {
      models: account.diagnostics.unpricedModels.join(", "),
    }));
  }
  if (account.sampleCount < 3 && account.status !== "excluded") {
    details.push(t("dashboard.weeklyCoverage.evidence.minimumIntervals", {
      count: account.sampleCount,
    }));
  }
  return details;
}

function independentIntervals(account: WeeklyCoverageAccount, now: string): WeeklyCoverageInterval[] {
  const start = Date.parse(now);
  const reset = account.resetAt ? Date.parse(account.resetAt) : NaN;
  if (account.quotaPaceStatus === "unavailable" || !Number.isFinite(reset) || reset <= start) return [];
  let exhaustion = reset;
  if (account.quotaPaceStatus === "exhausted") exhaustion = start;
  if (account.quotaPaceStatus === "exhausts_before_reset") {
    exhaustion = account.projectedExhaustionAt ? Date.parse(account.projectedExhaustionAt) : NaN;
    if (!Number.isFinite(exhaustion) || exhaustion >= reset) return [];
    exhaustion = Math.max(start, exhaustion);
  }
  const intervals: WeeklyCoverageInterval[] = [];
  if (exhaustion > start) intervals.push({ startAt: now, endAt: new Date(exhaustion).toISOString(), state: "available" });
  if (exhaustion < reset) intervals.push({ startAt: new Date(exhaustion).toISOString(), endAt: account.resetAt!, state: "exhausted" });
  return intervals;
}

function Timeline({ label, intervals, window, resetAt, repeatReset = false, kind = "account", dateFormat, t, testId }: {
  label: string;
  intervals: WeeklyCoverageInterval[];
  window: TimelineWindow;
  resetAt?: string | null;
  repeatReset?: boolean;
  kind?: "pool" | "account";
  dateFormat: DateFormat;
  t: Translation;
  testId: string;
}) {
  const segments = getCoverageTimelineSegments(intervals, window);
  const resets: number[] = [];
  if (window && resetAt) {
    const first = Date.parse(resetAt);
    for (let at = first; Number.isFinite(at) && at <= window.endMs; at += WEEK_MS) {
      if (at >= window.startMs) resets.push(at);
      if (!repeatReset) break;
    }
  }
  const descriptions: string[] = [];
  const describeSpan = (state: string, start: number, end: number) => {
    const startDate = formatCoverageDate(new Date(start).toISOString(), dateFormat);
    const endDate = formatCoverageDate(new Date(end).toISOString(), dateFormat);
    descriptions.push(`${state}, ${startDate}–${endDate}`);
  };
  let cursor = window?.startMs ?? 0;
  for (const segment of segments) {
    if (segment.startMs > cursor) {
      describeSpan(t("dashboard.weeklyCoverage.compact.unknown"), cursor, segment.startMs);
    }
    describeSpan(t(`dashboard.weeklyCoverage.interval.${segment.state}`), segment.startMs, segment.endMs);
    cursor = segment.endMs;
  }
  if (window && cursor < window.endMs) {
    describeSpan(t("dashboard.weeklyCoverage.compact.unknown"), cursor, window.endMs);
  }
  const description = descriptions.length
    ? `${label}: ${descriptions.join("; ")}`
    : t("dashboard.weeklyCoverage.timelineUnavailable", { label });
  const resetDescription = resets.map((at) => t("dashboard.weeklyCoverage.accountReset", {
    date: formatCoverageDate(new Date(at).toISOString(), dateFormat),
  })).join("; ");
  return (
    <div role="img" aria-label={[description, resetDescription].filter(Boolean).join("; ")} title={[description, resetDescription].filter(Boolean).join("; ")}
      data-testid={testId} className="relative h-6 bg-muted/50"
      style={{ backgroundImage: "repeating-linear-gradient(135deg, transparent, transparent 4px, var(--border) 4px, var(--border) 5px)" }}>
      <div className="absolute inset-0 overflow-hidden" aria-hidden="true">
        {segments.map((segment) => (
          <span key={`${segment.startAt}-${segment.state}`} data-state={segment.state}
            className={cn("absolute inset-y-0 flex items-center justify-center overflow-hidden text-[11px]", segment.state === "available"
              ? AVAILABLE_COLOR
              : kind === "pool" ? POOL_GAP_COLOR : "bg-muted")}
            style={{ left: `${segment.leftPercent}%`, width: `${segment.widthPercent}%` }}>
            {kind === "pool" && segment.state === "exhausted" && segment.widthPercent >= 8
              ? t("dashboard.weeklyCoverage.compact.gap") : null}
          </span>
        ))}
        {kind === "pool" && segments.length === 0 ? <span className="absolute inset-0 flex items-center justify-center text-[11px] text-muted-foreground">{t("dashboard.weeklyCoverage.compact.unknown")}</span> : null}
      </div>
      {window ? resets.map((at) => (
        <span key={at} aria-hidden="true" data-testid="weekly-coverage-reset-marker"
          className="absolute top-1/2 z-10 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rotate-45 border border-background bg-foreground"
          style={{ left: `${(at - window.startMs) / (window.endMs - window.startMs) * 100}%` }} />
      )) : null}
    </div>
  );
}

function accountOutcome(account: WeeklyCoverageAccount, now: string, t: Translation): string {
  const reset = Date.parse(account.resetAt ?? "");
  const start = Date.parse(now);
  const unknown = t("dashboard.weeklyCoverage.compact.unknown");
  if (account.quotaPaceStatus === "unavailable" || !Number.isFinite(reset) || reset <= start) return unknown;
  if (account.quotaPaceStatus === "no_usage") {
    return t("dashboard.weeklyCoverage.accountPace.noUsage");
  }
  if (account.quotaPaceStatus === "exhausts_before_reset" || account.quotaPaceStatus === "exhausted") {
    const exhaustion = account.quotaPaceStatus === "exhausted" ? start : Date.parse(account.projectedExhaustionAt ?? "");
    if (!Number.isFinite(exhaustion) || exhaustion >= reset) return unknown;
    return t("dashboard.weeklyCoverage.compact.gapDuration", { time: formatDuration(reset - Math.max(start, exhaustion), t) });
  }
  return account.projectedRemainingAtReset !== null
    ? t("dashboard.weeklyCoverage.compact.atReset", { percent: Math.round(account.projectedRemainingAtReset) })
    : t("dashboard.weeklyCoverage.compact.lasts");
}

function AccountEvidence({ account, generatedAt, dateFormat, t }: { account: WeeklyCoverageAccount; generatedAt: string; dateFormat: DateFormat; t: Translation }) {
  const evidence = accountEvidenceDetails(account, t);
  return (
    <div className="space-y-1 border-b border-border/60 py-3 last:border-0" data-testid={`weekly-coverage-account-evidence-${account.accountId}`}>
      <p className="break-all font-medium text-foreground">{account.label} <span className="font-normal text-muted-foreground">· {formatSlug(account.planType)}</span></p>
      <p>{account.reason ? t("dashboard.weeklyCoverage.accountReason", { reason: translatedCode(t, "dashboard.weeklyCoverage.reasons", account.reason) }) : null}</p>
      {account.status !== "excluded" ? <p>
        {account.remainingPercent !== null ? `${t("dashboard.weeklyCoverage.accountPace.barNow", { percent: formatCoveragePercent(account.remainingPercent) })} · ` : ""}
        {account.resetAt ? t("dashboard.weeklyCoverage.accountReset", { date: formatCoverageDate(account.resetAt, dateFormat) }) : ""}
      </p> : null}
      {account.quotaPaceStatus === "exhausts_before_reset" && account.projectedExhaustionAt ? <p>{t("dashboard.weeklyCoverage.accountPace.exhausts", { date: formatCoverageDate(account.projectedExhaustionAt, dateFormat) })}</p> : null}
      {account.status !== "excluded" && account.quotaPaceStatus !== "unavailable" ? <p>{accountOutcome(account, generatedAt, t)}{account.usedPercentPerDay !== null ? ` · ${t("dashboard.weeklyCoverage.accountPace.rate", { percent: formatCoveragePercent(account.usedPercentPerDay) })}` : ""}</p> : null}
      <p>{t("dashboard.weeklyCoverage.accountSamples")}: {account.sampleCount}</p>
      {evidence.length ? <ul className="list-disc space-y-1 pl-4">{evidence.map((detail) => <li key={detail}>{detail}</li>)}</ul> : null}
    </div>
  );
}

export function WeeklyCoverageCard({ coverage }: WeeklyCoverageCardProps) {
  const { t } = useTranslation();
  const dateFormat = useDateDisplayFormatStore((state) => state.dateDisplayFormat);
  const [visibleDays, setVisibleDays] = useState(7);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const headingId = useId();
  if (!coverage) return null;

  const ready = coverage.status === "ready";
  const window = getCoverageWindow(coverage, visibleDays);
  const included = coverage.accounts.filter((account) => account.status !== "excluded");
  const excluded = coverage.accounts.filter((account) => account.status === "excluded");
  const gap = ready ? findFirstCoverageGap(coverage) : null;
  const recovery = gap ? getCoverageTimelineSegments(coverage.intervals, getCoverageWindow(coverage, 14))
    .find((interval) => interval.state === "available" && interval.startMs >= gap.endMs) : null;
  const headline = ready
    ? gap
      ? gap.startMs <= Date.parse(coverage.generatedAt)
        ? t("dashboard.weeklyCoverage.compact.gapNow")
        : t("dashboard.weeklyCoverage.compact.gapSoon", { time: formatDuration(gap.startMs - Date.parse(coverage.generatedAt), t) })
      : t("dashboard.weeklyCoverage.compact.covered", { days: getCoverageHorizonDays(coverage) })
    : t(coverage.status === "no_eligible_accounts" ? "dashboard.weeklyCoverage.compact.noAccounts" : coverage.status === "learning" ? "dashboard.weeklyCoverage.compact.learning" : "dashboard.weeklyCoverage.compact.unavailable");
  const axisDays = window ? (window.endMs - window.startMs) / (WEEK_MS / 7) : visibleDays;
  const ticks = [0, axisDays];
  const resetTicks = included
    .flatMap((account) => {
      const day = (Date.parse(account.resetAt ?? "") - Date.parse(coverage.generatedAt)) / (WEEK_MS / 7);
      return ready ? [day, day + 7] : [day];
    })
    .filter((day) => Number.isFinite(day) && day >= 0 && day <= axisDays)
    .sort((left, right) => left - right)
    .reduce<number[]>((days, day) => {
      // Nearby resets share a label; every account still keeps its own diamond.
      if (days.length === 0 || day - days[days.length - 1] >= axisDays * 0.1) days.push(day);
      return days;
    }, []);

  return (
    <section aria-labelledby={headingId} data-testid="weekly-coverage-card" className="rounded-xl border bg-card px-4 py-4 sm:px-5">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 id={headingId} className="text-sm font-semibold">{t("dashboard.weeklyCoverage.title")}</h2>
          <p className={cn("mt-0.5 text-xs", ready && gap ? "text-red-700 dark:text-red-300" : "text-muted-foreground")}>{headline}</p>
        </div>
        <div className="flex shrink-0 rounded-md bg-muted/60 p-0.5" role="group" aria-label={t("dashboard.weeklyCoverage.horizonLabel")}>
          {[7, 14].map((days) => <button key={days} type="button" aria-pressed={visibleDays === days}
            aria-label={t("dashboard.weeklyCoverage.showHorizon", { days })} data-testid={`weekly-coverage-horizon-${days}`}
            onClick={() => setVisibleDays(days)} className={cn("rounded px-2 py-1 text-[11px] tabular-nums focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring", visibleDays === days ? "bg-background font-medium shadow-sm" : "text-muted-foreground")}>{days}d</button>)}
        </div>
      </div>
      <div className={cn(ROW_GRID, "mb-2 text-[10px] text-muted-foreground")} data-testid="weekly-coverage-axis">
        <span />
        <div className="relative h-4">{ticks.map((day, index) => <span key={day}
          className="absolute whitespace-nowrap" style={{ left: `${day / axisDays * 100}%`, transform: index === 0 ? undefined : index === ticks.length - 1 ? "translateX(-100%)" : "translateX(-50%)" }}>
          {day === 0 ? t("dashboard.weeklyCoverage.now") : `+${Number(day.toFixed(1))}d`}
        </span>)}</div>
      </div>
      <div className={cn(ROW_GRID, "mb-2 border-b border-border/60 pb-3")}>
        <span className="text-xs font-semibold">{t("dashboard.weeklyCoverage.poolLabel")}</span>
        <Timeline kind="pool" label={t("dashboard.weeklyCoverage.poolLabel")} intervals={ready ? coverage.intervals : []} window={window} dateFormat={dateFormat} t={t} testId="weekly-coverage-pool-timeline" />
      </div>
      <div className="space-y-2" data-testid="weekly-coverage-accounts">
        {included.map((account) => {
          const intervals = ready ? account.intervals : independentIntervals(account, coverage.generatedAt);
          return <div key={account.accountId} className={ROW_GRID}>
            <span className="truncate text-xs text-muted-foreground" title={account.label}>{account.label}</span>
            <Timeline label={account.label} intervals={intervals} window={window} resetAt={account.resetAt} repeatReset={ready} dateFormat={dateFormat} t={t} testId={`weekly-coverage-account-timeline-${account.accountId}`} />
          </div>;
        })}
      </div>
      {resetTicks.length > 0 ? <div className={cn(ROW_GRID, "mt-2 text-[10px] text-muted-foreground")} aria-hidden="true">
        <span />
        <div className="relative h-4">{resetTicks.map((day) => {
          const { days, hours, minutes } = getCoverageDurationParts(day * WEEK_MS / 7);
          const label = [days ? `${days}d` : "", hours ? `${hours}h` : ""].filter(Boolean).join(" ") || `${minutes}m`;
          return <span key={day} className="absolute whitespace-nowrap"
            style={{ left: `${day / axisDays * 100}%`, transform: day / axisDays < 0.05 ? undefined : day / axisDays > 0.95 ? "translateX(-100%)" : "translateX(-50%)" }}>{label}</span>;
        })}</div>
      </div> : null}
      {ready && visibleDays === 7 && isGapOutsideDefaultWindow(coverage) ? <p data-testid="weekly-coverage-gap-beyond-default" className="mt-2 text-[11px] text-red-700 dark:text-red-300">{t("dashboard.weeklyCoverage.gapBeyondDefault", { days: 7 })}</p> : null}
      {!ready && included.length > 0 ? <p className="mt-3 text-[11px] text-muted-foreground">{t("dashboard.weeklyCoverage.compact.independent")}</p> : null}
      <Collapsible open={detailsOpen} onOpenChange={setDetailsOpen}>
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-muted-foreground" aria-label={t("dashboard.weeklyCoverage.compact.legend")}>
            <span className="inline-flex items-center gap-1"><span aria-hidden="true" className={cn("h-2 w-3", AVAILABLE_COLOR)} />{t("dashboard.weeklyCoverage.interval.available")}</span>
            <span className="inline-flex items-center gap-1"><span aria-hidden="true" className={cn("h-2 w-3", ready ? POOL_GAP_COLOR : "bg-muted")} />{t(ready ? "dashboard.weeklyCoverage.compact.poolGap" : "dashboard.weeklyCoverage.compact.empty")}</span>
            <span className="inline-flex items-center gap-1"><span aria-hidden="true" className="mx-0.5 h-1.5 w-1.5 rotate-45 bg-foreground" />{t("dashboard.weeklyCoverage.compact.reset")}</span>
            {!ready ? <span className="inline-flex items-center gap-1"><span aria-hidden="true" className="h-2 w-3 bg-muted" style={{ backgroundImage: "repeating-linear-gradient(135deg, transparent, transparent 2px, var(--border) 2px, var(--border) 3px)" }} />{t("dashboard.weeklyCoverage.compact.unknown")}</span> : null}
          </div>
          <CollapsibleTrigger asChild><button type="button" className="inline-flex items-center gap-1 rounded py-1 text-[11px] text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            {t("dashboard.weeklyCoverage.compact.details")}<ChevronRight aria-hidden="true" className={cn("h-3 w-3 transition-transform", detailsOpen && "rotate-90")} />
          </button></CollapsibleTrigger>
        </div>
        <CollapsibleContent>
          <div className="mt-3 border-t pt-3 text-xs text-muted-foreground" data-testid="weekly-coverage-details">
            {gap ? <p>{recovery ? t("dashboard.weeklyCoverage.description.interruption", { start: formatCoverageDate(new Date(gap.startMs).toISOString(), dateFormat), end: formatCoverageDate(new Date(recovery.startMs).toISOString(), dateFormat), duration: formatDuration(gap.endMs - gap.startMs, t) }) : t("dashboard.weeklyCoverage.description.interruptionUntilHorizon", { start: formatCoverageDate(new Date(gap.startMs).toISOString(), dateFormat), days: getCoverageHorizonDays(coverage) })}</p> : null}
            {ready && coverage.minimumReserveHours !== null ? <p>{t("dashboard.weeklyCoverage.minimumReserve", { reserve: formatReserveHours(coverage.minimumReserveHours, t), at: coverage.minimumReserveAt ? formatCoverageDate(coverage.minimumReserveAt, dateFormat) : t("dashboard.weeklyCoverage.unknownTime") })}</p> : null}
            {coverage.accounts.map((account) => <AccountEvidence key={account.accountId} account={account} generatedAt={coverage.generatedAt} dateFormat={dateFormat} t={t} />)}
            {excluded.length > 0 ? <p className="mt-2" data-testid="weekly-coverage-excluded-summary">{t("dashboard.weeklyCoverage.excludedSummary", { count: excluded.length })}</p> : null}
            {coverage.warnings.length > 0 ? <ul className="mt-3 list-disc space-y-1 pl-4">{coverage.warnings.map((warning) => <li key={warning}>{translatedCode(t, "dashboard.weeklyCoverage.warnings", warning)}</li>)}</ul> : null}
            <div className="mt-3 space-y-1">
              <p>{t("dashboard.weeklyCoverage.assumption", { basis: t("dashboard.weeklyCoverage.paceBasis.currentWindowAverage") })}</p>
              <p>{t("dashboard.weeklyCoverage.routingNote", { strategy: formatSlug(coverage.routingStrategy) })}</p>
              <p>{t("dashboard.weeklyCoverage.scopeNote")}</p>
            </div>
          </div>
        </CollapsibleContent>
      </Collapsible>
    </section>
  );
}
