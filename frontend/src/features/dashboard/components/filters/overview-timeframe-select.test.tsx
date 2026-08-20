import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import i18n from "@/i18n";
import { OverviewTimeframeSelect } from "./overview-timeframe-select";

describe("OverviewTimeframeSelect", () => {
  beforeEach(async () => {
    await i18n.changeLanguage("en");
  });

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

  it("preserves an inverted start-date draft until the end date makes it valid", async () => {
    const user = userEvent.setup();
    const onCustomRangeChange = vi.fn();

    render(
      <OverviewTimeframeSelect
        value={{ mode: "custom", startDate: "2026-06-01", endDate: "2026-06-07" }}
        onPresetSelect={vi.fn()}
        onCustomRangeChange={onCustomRangeChange}
      />,
    );

    await user.click(screen.getByRole("button", { name: /Custom range/i }));
    const startInput = screen.getByLabelText("Dashboard overview start date");
    const endInput = screen.getByLabelText("Dashboard overview end date");

    fireEvent.change(startInput, { target: { value: "2026-06-10" } });

    expect(startInput).toHaveValue("2026-06-10");
    expect(onCustomRangeChange).not.toHaveBeenCalled();

    fireEvent.change(endInput, { target: { value: "2026-06-12" } });

    expect(onCustomRangeChange).toHaveBeenCalledOnce();
    expect(onCustomRangeChange).toHaveBeenCalledWith({
      startDate: "2026-06-10",
      endDate: "2026-06-12",
    });
  });

  it.each([
    {
      language: "ko",
      buttonName: /사용자 지정 기간: 2026-06-01부터 2026-06-07까지/,
      startLabel: "Dashboard 개요 시작일",
      endLabel: "Dashboard 개요 종료일",
    },
    {
      language: "zh-CN",
      buttonName: /自定义范围：2026-06-01 至 2026-06-07/,
      startLabel: "仪表盘概览开始日期",
      endLabel: "仪表盘概览结束日期",
    },
  ])("localizes custom-range controls in $language", async ({ language, buttonName, startLabel, endLabel }) => {
    await i18n.changeLanguage(language);
    const user = userEvent.setup();

    render(
      <OverviewTimeframeSelect
        value={{ mode: "custom", startDate: "2026-06-01", endDate: "2026-06-07" }}
        onPresetSelect={vi.fn()}
        onCustomRangeChange={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: buttonName }));

    expect(screen.getByLabelText(startLabel)).toBeInTheDocument();
    expect(screen.getByLabelText(endLabel)).toBeInTheDocument();
  });
});
