import { CalendarIcon, ChevronDown } from "lucide-react";
import type { DateRange } from "react-day-picker";

import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import type {
  DashboardOverviewRange,
  OverviewTimeframe,
} from "@/features/dashboard/schemas";
import { localDateISO } from "@/features/reports/date";

const PRESETS = [
  { label: "1d", timeframe: "1d" },
  { label: "7d", timeframe: "7d" },
  { label: "30d", timeframe: "30d" },
] as const satisfies ReadonlyArray<{ label: string; timeframe: OverviewTimeframe }>;

export type OverviewTimeframeSelectProps = {
  value: DashboardOverviewRange;
  onPresetSelect: (value: OverviewTimeframe) => void;
  onCustomRangeChange: (range: Pick<Extract<DashboardOverviewRange, { mode: "custom" }>, "startDate" | "endDate">) => void;
};

export function OverviewTimeframeSelect({
  value,
  onPresetSelect,
  onCustomRangeChange,
}: OverviewTimeframeSelectProps) {
  const maxDate = localDateISO();
  const maxSelectableDate = parseLocalDate(maxDate);
  const customRange =
    value.mode === "custom"
      ? value
      : {
          startDate: daysAgoLocalISO(6),
          endDate: maxDate,
        };
  const selectedRange = buildSelectedRange(customRange.startDate, customRange.endDate);

  const updateRange = (range: Partial<Pick<typeof customRange, "startDate" | "endDate">>) => {
    onCustomRangeChange({
      startDate: clampDateInputValue(range.startDate ?? customRange.startDate, maxDate),
      endDate: clampDateInputValue(range.endDate ?? customRange.endDate, maxDate),
    });
  };

  const handleCalendarRangeSelect = (range: DateRange | undefined) => {
    if (!range?.from) {
      return;
    }
    const startDate = clampDateInputValue(localDateISO(range.from), maxDate);
    const endDate = clampDateInputValue(range.to ? localDateISO(range.to) : startDate, maxDate);
    onCustomRangeChange({ startDate, endDate });
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      {PRESETS.map((preset) => {
        const isSelected = value.mode === "preset" && value.timeframe === preset.timeframe;

        return (
          <Button
            key={preset.timeframe}
            type="button"
            variant={isSelected ? "default" : "outline"}
            size="sm"
            aria-pressed={isSelected}
            onClick={() => onPresetSelect(preset.timeframe)}
          >
            {preset.label}
          </Button>
        );
      })}

      <Popover>
        <PopoverTrigger asChild>
          <Button
            type="button"
            variant={value.mode === "custom" ? "default" : "outline"}
            size="sm"
            aria-pressed={value.mode === "custom"}
            aria-label={`Custom range ${customRange.startDate} to ${customRange.endDate}`}
            className="gap-1.5"
          >
            <CalendarIcon className="h-3.5 w-3.5" aria-hidden="true" />
            <span>Custom</span>
            <span className="hidden text-xs font-normal opacity-80 sm:inline">
              {customRange.startDate} - {customRange.endDate}
            </span>
            <ChevronDown className="h-3.5 w-3.5 opacity-60" aria-hidden="true" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-auto min-w-[320px] p-3" align="end">
          <div className="grid gap-3">
            <div className="grid grid-cols-2 gap-2">
              <label className="grid gap-1 text-xs font-medium text-muted-foreground">
                Start
                <input
                  type="date"
                  aria-label="Dashboard overview start date"
                  max={maxDate}
                  value={customRange.startDate}
                  onChange={(event) => updateRange({ startDate: event.target.value })}
                  className="h-8 rounded-md border bg-transparent px-2 text-xs text-foreground"
                />
              </label>
              <label className="grid gap-1 text-xs font-medium text-muted-foreground">
                End
                <input
                  type="date"
                  aria-label="Dashboard overview end date"
                  max={maxDate}
                  value={customRange.endDate}
                  onChange={(event) => updateRange({ endDate: event.target.value })}
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

function clampDateInputValue(value: string, maxDate: string): string {
  if (!parseLocalDate(value) || !parseLocalDate(maxDate)) {
    return value;
  }
  return value > maxDate ? maxDate : value;
}

function daysAgoLocalISO(days: number, date: Date = new Date()): string {
  const shifted = new Date(date);
  shifted.setDate(shifted.getDate() - days);
  return localDateISO(shifted);
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
