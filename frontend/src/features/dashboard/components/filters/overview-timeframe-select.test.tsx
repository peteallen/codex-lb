import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { OverviewTimeframeSelect } from "./overview-timeframe-select";

describe("OverviewTimeframeSelect", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders quick presets and forwards preset clicks", () => {
    const onPresetSelect = vi.fn();

    render(
      <OverviewTimeframeSelect
        value={{ mode: "preset", timeframe: "7d" }}
        onPresetSelect={onPresetSelect}
        onCustomRangeChange={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "1d" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: "7d" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "30d" })).toHaveAttribute("aria-pressed", "false");

    fireEvent.click(screen.getByRole("button", { name: "30d" }));

    expect(onPresetSelect).toHaveBeenCalledWith("30d");
  });

  it("shows the custom range picker and updates dates", async () => {
    const user = userEvent.setup();
    const onCustomRangeChange = vi.fn();

    render(
      <OverviewTimeframeSelect
        value={{ mode: "custom", startDate: "2026-06-01", endDate: "2026-06-07" }}
        onPresetSelect={vi.fn()}
        onCustomRangeChange={onCustomRangeChange}
      />,
    );

    const customButton = screen.getByRole("button", {
      name: /Custom range 2026-06-01 to 2026-06-07/i,
    });
    expect(customButton).toHaveAttribute("aria-pressed", "true");

    await user.click(customButton);
    fireEvent.change(screen.getByLabelText("Dashboard overview start date"), {
      target: { value: "2026-05-15" },
    });

    expect(onCustomRangeChange).toHaveBeenCalledWith({
      startDate: "2026-05-15",
      endDate: "2026-06-07",
    });
  });

  it("limits custom range inputs to the current browser-local day", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-12T12:00:00"));
    const onCustomRangeChange = vi.fn();

    render(
      <OverviewTimeframeSelect
        value={{ mode: "custom", startDate: "2026-06-01", endDate: "2026-06-07" }}
        onPresetSelect={vi.fn()}
        onCustomRangeChange={onCustomRangeChange}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Custom/i }));

    expect(screen.getByLabelText("Dashboard overview start date")).toHaveAttribute("max", "2026-06-12");
    expect(screen.getByLabelText("Dashboard overview end date")).toHaveAttribute("max", "2026-06-12");

    fireEvent.change(screen.getByLabelText("Dashboard overview end date"), {
      target: { value: "2026-06-20" },
    });

    expect(onCustomRangeChange).toHaveBeenCalledWith({
      startDate: "2026-06-01",
      endDate: "2026-06-12",
    });
  });
});
