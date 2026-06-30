import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ReportsFilters, type ReportsFiltersState } from "./reports-filters";

const FILTERS: ReportsFiltersState = {
  startDate: "2026-06-01",
  endDate: "2026-06-07",
  accountId: [],
  model: "",
  useragent: "",
};

describe("ReportsFilters", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("updates account filters from the account selector", async () => {
    const user = userEvent.setup();
    const onFiltersChange = vi.fn();
    render(
      <ReportsFilters
        filters={FILTERS}
        selectedPresetDays={7}
        accountOptions={[{ value: "acc_one", label: "Primary account", isEmail: false }]}
        modelOptions={[]}
        useragentOptions={[]}
        onPresetSelect={vi.fn()}
        onFiltersChange={onFiltersChange}
      />,
    );

    await user.click(screen.getByRole("button", { name: /accounts/i }));
    await user.click(await screen.findByRole("menuitemcheckbox", { name: /primary account/i }));

    expect(onFiltersChange).toHaveBeenCalledWith({ ...FILTERS, accountId: ["acc_one"] });
  });

  it("keeps the reports model filter as a single selected value", async () => {
    const user = userEvent.setup();
    const onFiltersChange = vi.fn();
    render(
      <ReportsFilters
        filters={{ ...FILTERS, model: "gpt-5.1" }}
        selectedPresetDays={7}
        accountOptions={[]}
        modelOptions={[
          { value: "gpt-5.1", label: "gpt-5.1" },
          { value: "gpt-5.2", label: "gpt-5.2" },
        ]}
        useragentOptions={[]}
        onPresetSelect={vi.fn()}
        onFiltersChange={onFiltersChange}
      />,
    );

    await user.click(screen.getByRole("button", { name: /gpt-5.1/i }));
    await user.click(await screen.findByRole("menuitemcheckbox", { name: /gpt-5.2/i }));

    expect(onFiltersChange).toHaveBeenCalledWith({
      ...FILTERS,
      model: "gpt-5.2",
    });
  });

  it("keeps the reports user-agent filter as a single selected value", async () => {
    const user = userEvent.setup();
    const onFiltersChange = vi.fn();
    render(
      <ReportsFilters
        filters={{ ...FILTERS, useragent: "CLI" }}
        selectedPresetDays={7}
        accountOptions={[]}
        modelOptions={[]}
        useragentOptions={[
          { value: "CLI", label: "CLI" },
          { value: "SDK", label: "SDK" },
        ]}
        onPresetSelect={vi.fn()}
        onFiltersChange={onFiltersChange}
      />,
    );

    await user.click(screen.getByRole("button", { name: /^CLI$/i }));
    await user.click(await screen.findByRole("menuitemcheckbox", { name: /^SDK$/i }));

    expect(onFiltersChange).toHaveBeenCalledWith({
      ...FILTERS,
      useragent: "SDK",
    });
  });

  it("renders the selected preset as pressed and forwards preset clicks", () => {
    const onFiltersChange = vi.fn();
    const onPresetSelect = vi.fn();

    render(
      <ReportsFilters
        filters={FILTERS}
        selectedPresetDays={30}
        accountOptions={[]}
        modelOptions={[]}
        useragentOptions={[]}
        onPresetSelect={onPresetSelect}
        onFiltersChange={onFiltersChange}
      />,
    );

    const button1d = screen.getByRole("button", { name: "1d" });
    const button7d = screen.getByRole("button", { name: "7d" });
    const button30d = screen.getByRole("button", { name: "30d" });
    const customButton = screen.getByRole("button", {
      name: /Custom range 2026-06-01 to 2026-06-07/i,
    });

    expect(button1d).toHaveAttribute("aria-pressed", "false");
    expect(button7d).toHaveAttribute("aria-pressed", "false");
    expect(button7d).toHaveAttribute("data-variant", "outline");
    expect(button30d).toHaveAttribute("aria-pressed", "true");
    expect(button30d).toHaveAttribute("data-variant", "default");
    expect(customButton).toHaveAttribute("aria-pressed", "false");
    expect(screen.queryByRole("button", { name: "90d" })).not.toBeInTheDocument();

    fireEvent.click(button1d);

    expect(onPresetSelect).toHaveBeenCalledWith(1);
  });

  it("shows the custom range picker and updates date filters", async () => {
    const user = userEvent.setup();
    const onFiltersChange = vi.fn();

    render(
      <ReportsFilters
        filters={FILTERS}
        selectedPresetDays={null}
        accountOptions={[]}
        modelOptions={[]}
        useragentOptions={[]}
        onPresetSelect={vi.fn()}
        onFiltersChange={onFiltersChange}
      />,
    );

    const customButton = screen.getByRole("button", {
      name: /Custom range 2026-06-01 to 2026-06-07/i,
    });
    expect(customButton).toHaveAttribute("aria-pressed", "true");
    expect(customButton).toHaveAttribute("data-variant", "default");

    await user.click(customButton);
    fireEvent.change(screen.getByLabelText("Start date"), {
      target: { value: "2026-05-15" },
    });
    fireEvent.change(screen.getByLabelText("End date"), {
      target: { value: "2026-06-10" },
    });

    expect(onFiltersChange).toHaveBeenCalledWith({
      ...FILTERS,
      startDate: "2026-05-15",
    });
    expect(onFiltersChange).toHaveBeenCalledWith({
      ...FILTERS,
      endDate: "2026-06-10",
    });
  });

  it("limits both custom range date inputs to the current browser-local day", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-12T12:00:00"));
    const onFiltersChange = vi.fn();

    render(
      <ReportsFilters
        filters={FILTERS}
        selectedPresetDays={30}
        accountOptions={[]}
        modelOptions={[]}
        useragentOptions={[]}
        onPresetSelect={vi.fn()}
        onFiltersChange={onFiltersChange}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Custom/i }));

    expect(screen.getByLabelText("Start date")).toHaveAttribute("max", "2026-06-12");
    expect(screen.getByLabelText("End date")).toHaveAttribute("max", "2026-06-12");

    fireEvent.change(screen.getByLabelText("End date"), {
      target: { value: "2026-06-20" },
    });

    expect(onFiltersChange).toHaveBeenCalledWith({
      ...FILTERS,
      endDate: "2026-06-12",
    });
  });
});
