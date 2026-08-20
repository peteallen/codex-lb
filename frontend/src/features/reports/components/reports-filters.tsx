import { useId } from "react";
import { Button } from "@/components/ui/button";
import { useTranslation } from "react-i18next";
import {
  MultiSelectFilter,
  type MultiSelectOption,
} from "@/features/dashboard/components/filters/multi-select-filter";
import { isReportDateRangeValid, localDateISO } from "../date";
import {
  REPORT_CHART_DEFINITIONS,
  type ReportChartId,
} from "../hooks/use-report-chart-visibility";

export type ReportsFiltersState = {
  startDate: string;
  endDate: string;
  accountId: string[];
  apiKeyId: string[];
  model: string;
  useragent: string;
};

export type ReportsFiltersProps = {
  filters: ReportsFiltersState;
  selectedPresetDays: number | null;
  accountOptions: MultiSelectOption[];
  apiKeyOptions: MultiSelectOption[];
  modelOptions: MultiSelectOption[];
  useragentOptions: MultiSelectOption[];
  visibleChartIds: ReportChartId[];
  onPresetSelect: (days: number) => void;
  onFiltersChange: (filters: ReportsFiltersState) => void;
  onVisibleChartIdsChange: (ids: string[]) => void;
};

const PRESETS = [
  { label: "1d", days: 1 },
  { label: "7d", days: 7 },
  { label: "30d", days: 30 },
] as const;

export function ReportsFilters({
  filters,
  selectedPresetDays,
  accountOptions,
  apiKeyOptions,
  modelOptions,
  useragentOptions,
  visibleChartIds,
  onPresetSelect,
  onFiltersChange,
  onVisibleChartIdsChange,
}: ReportsFiltersProps) {
  const { t } = useTranslation();
  const chartOptions = REPORT_CHART_DEFINITIONS.map(({ id, labelKey }) => ({
    value: id,
    label: t(labelKey),
  }));
  const maxDate = localDateISO();
  const dateRangeErrorId = useId();
  const isDateRangeInvalid = !isReportDateRangeValid(
    filters.startDate,
    filters.endDate,
  );
  const startDateMax =
    filters.endDate && filters.endDate < maxDate ? filters.endDate : maxDate;

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-xl border bg-card p-3">
      <div className="flex flex-wrap items-center gap-2">
        {PRESETS.map((preset) => {
          const isSelected = selectedPresetDays === preset.days;

          return (
            <Button
              key={preset.days}
              variant={isSelected ? "default" : "outline"}
              size="sm"
              aria-pressed={isSelected}
              onClick={() => onPresetSelect(preset.days)}
            >
              {preset.label}
            </Button>
          );
        })}

        <Popover>
          <PopoverTrigger asChild>
            <Button
              type="button"
              variant={selectedPresetDays === null ? "default" : "outline"}
              size="sm"
              aria-pressed={selectedPresetDays === null}
              aria-label={`Custom range ${filters.startDate} to ${filters.endDate}`}
              className="gap-1.5"
            >
              <CalendarIcon className="h-3.5 w-3.5" aria-hidden="true" />
              <span>Custom</span>
              <span className="hidden text-xs font-normal opacity-80 sm:inline">
                {filters.startDate} - {filters.endDate}
              </span>
              <ChevronDown className="h-3.5 w-3.5 opacity-60" aria-hidden="true" />
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-auto min-w-[320px] p-3" align="start">
            <div className="grid gap-3">
              <div className="grid grid-cols-2 gap-2">
                <label className="grid gap-1 text-xs font-medium text-muted-foreground">
                  Start
                  <input
                    type="date"
                    aria-label="Start date"
                    max={maxDate}
                    value={filters.startDate}
                    onChange={(e) => updateRange({ startDate: e.target.value })}
                    className="h-8 rounded-md border bg-transparent px-2 text-xs text-foreground"
                  />
                </label>
                <label className="grid gap-1 text-xs font-medium text-muted-foreground">
                  End
                  <input
                    type="date"
                    aria-label="End date"
                    max={maxDate}
                    value={filters.endDate}
                    onChange={(e) => updateRange({ endDate: e.target.value })}
                    className="h-8 rounded-md border bg-transparent px-2 text-xs text-foreground"
                  />
                </label>
              </div>
              <Calendar
                mode="range"
                selected={selectedRange}
                onSelect={handleCalendarRangeSelect}
                disabled={(date) => (maxSelectableDate ? date > maxSelectableDate : false)}
                className="rounded-md border"
                autoFocus
              />
            </div>
          </PopoverContent>
        </Popover>
      </div>

      <MultiSelectFilter
        label={t("dashboard.filters.accounts")}
        values={filters.accountId}
        options={accountOptions}
        onChange={(accountId) => onFiltersChange({ ...filters, accountId })}
      />
      <MultiSelectFilter
        label={t("reports.filters.apiKeys")}
        values={filters.apiKeyId}
        options={apiKeyOptions}
        onChange={(apiKeyId) => onFiltersChange({ ...filters, apiKeyId })}
      />
      <MultiSelectFilter
        label={t("dashboard.filters.model")}
        values={filters.model ? [filters.model] : []}
        options={modelOptions}
        onChange={(models) =>
          onFiltersChange({ ...filters, model: models.at(-1) ?? "" })
        }
      />
      <MultiSelectFilter
        label={t("reports.filters.userAgent")}
        values={filters.useragent ? [filters.useragent] : []}
        options={useragentOptions}
        onChange={(useragents) =>
          onFiltersChange({ ...filters, useragent: useragents.at(-1) ?? "" })
        }
      />

      <MultiSelectFilter
        label={t("reports.filters.charts")}
        values={visibleChartIds}
        options={chartOptions}
        onChange={onVisibleChartIdsChange}
      />

      <div className="ml-auto flex flex-col items-end gap-1">
        <div className="flex items-center gap-2">
          <input
            type="date"
            name="report-start-date"
            autoComplete="off"
            aria-label={t("reports.filters.startDate")}
            aria-invalid={isDateRangeInvalid || undefined}
            aria-describedby={isDateRangeInvalid ? dateRangeErrorId : undefined}
            max={startDateMax}
            value={filters.startDate}
            onChange={(e) =>
              onFiltersChange({ ...filters, startDate: e.target.value })
            }
            className="h-8 rounded-md border bg-transparent px-2 text-xs text-foreground aria-invalid:border-destructive aria-invalid:ring-destructive/20"
          />
          <span aria-hidden="true" className="text-xs text-muted-foreground">
            —
          </span>
          <input
            type="date"
            name="report-end-date"
            autoComplete="off"
            aria-label={t("reports.filters.endDate")}
            aria-invalid={isDateRangeInvalid || undefined}
            aria-describedby={isDateRangeInvalid ? dateRangeErrorId : undefined}
            min={filters.startDate || undefined}
            max={maxDate}
            value={filters.endDate}
            onChange={(e) =>
              onFiltersChange({ ...filters, endDate: e.target.value })
            }
            className="h-8 rounded-md border bg-transparent px-2 text-xs text-foreground aria-invalid:border-destructive aria-invalid:ring-destructive/20"
          />
        </div>
        {isDateRangeInvalid ? (
          <p
            id={dateRangeErrorId}
            aria-live="polite"
            className="text-xs text-destructive"
          >
            {t("reports.filters.invalidDateRange")}
          </p>
        ) : null}
      </div>
    </div>
  );
}

function buildSelectedRange(startDate: string, endDate: string): DateRange | undefined {
  const from = parseLocalDate(startDate);
  const to = parseLocalDate(endDate);
  if (!from && !to) {
    return undefined;
  }
  return { from, to };
}

function clampDateRange(
  range: Partial<Pick<ReportsFiltersState, "startDate" | "endDate">>,
  maxDate: string,
): Partial<Pick<ReportsFiltersState, "startDate" | "endDate">> {
  const clampedRange: Partial<Pick<ReportsFiltersState, "startDate" | "endDate">> = {};
  if (range.startDate !== undefined) {
    clampedRange.startDate = clampDateInputValue(range.startDate, maxDate);
  }
  if (range.endDate !== undefined) {
    clampedRange.endDate = clampDateInputValue(range.endDate, maxDate);
  }
  return clampedRange;
}

function clampDateInputValue(value: string, maxDate: string): string {
  if (!parseLocalDate(value) || !parseLocalDate(maxDate)) {
    return value;
  }
  return value > maxDate ? maxDate : value;
}

function parseLocalDate(value: string): Date | undefined {
  const [yearText, monthText, dayText] = value.split("-");
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  if (!year || !month || !day) {
    return undefined;
  }

  const date = new Date(year, month - 1, day);
  if (
    date.getFullYear() !== year ||
    date.getMonth() !== month - 1 ||
    date.getDate() !== day
  ) {
    return undefined;
  }

  return date;
}
