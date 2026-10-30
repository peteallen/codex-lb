import { describe, expect, it } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { WeeklyCoverage } from "@/features/dashboard/schemas";
import { renderWithProviders } from "@/test/utils";

import { WeeklyCoverageCard } from "./weekly-coverage-card";

const GENERATED_AT = "2026-01-01T12:00:00.000Z";
const HORIZON_AT = "2026-01-15T12:00:00.000Z";
const RESET_AT = "2026-01-08T12:00:00.000Z";

function interval(startAt: string, endAt: string, state: "available" | "exhausted") {
  return { startAt, endAt, state };
}

function account(
  overrides: Partial<WeeklyCoverage["accounts"][number]> = {},
): WeeklyCoverage["accounts"][number] {
  return {
    accountId: "account-a",
    label: "Account A",
    planType: "pro",
    status: "ready",
    reason: null,
    remainingPercent: 68,
    resetAt: RESET_AT,
    capacityWorkUnits: 10_000,
    sampleCount: 8,
    observedDropPercent: 12,
    intervals: [interval(GENERATED_AT, HORIZON_AT, "available")],
    quotaPaceStatus: "lasts_until_reset",
    usedPercentPerDay: 4.5,
    projectedExhaustionAt: null,
    projectedRemainingAtReset: 40,
    diagnostics: {
      discardedIntervalCount: 0,
      unpricedModels: [],
    },
    ...overrides,
  };
}

function coverage(overrides: Partial<WeeklyCoverage> = {}): WeeklyCoverage {
  return {
    status: "ready",
    generatedAt: GENERATED_AT,
    horizonAt: HORIZON_AT,
    paceBasis: "current_window_average",
    routingStrategy: "reset_drain",
    warnings: [],
    accounts: [account()],
    intervals: [interval(GENERATED_AT, HORIZON_AT, "available")],
    minimumReserveHours: 18.5,
    minimumReserveAt: "2026-01-05T12:00:00.000Z",
    ...overrides,
  };
}

function timelineFor(testId: string) {
  const container = screen.getByTestId(testId);
  return container.getAttribute("role") === "img" ? container : within(container).getByRole("img");
}

function expectClosedDetails() {
  const trigger = screen.getByRole("button", { name: "Details" });
  expect(trigger).toHaveAttribute("aria-expanded", "false");
  const details = screen.queryByTestId("weekly-coverage-details");
  if (details) expect(details).not.toBeVisible();
}

describe("WeeklyCoverageCard", () => {
  it("keeps the ready state to one shared axis and compact account rows", () => {
    renderWithProviders(
      <WeeklyCoverageCard
        coverage={coverage({
          accounts: [
            account(),
            account({ accountId: "account-b", label: "Account B", resetAt: "2026-01-10T12:00:00.000Z" }),
          ],
        })}
      />,
    );

    expect(screen.getByTestId("weekly-coverage-card")).toBeInTheDocument();
    expect(screen.getByText("No gap projected over 14 days")).toBeInTheDocument();
    expect(screen.getByTestId("weekly-coverage-axis")).toBeInTheDocument();
    expect(screen.getByTestId("weekly-coverage-pool-timeline")).toBeInTheDocument();
    expect(screen.getByTestId("weekly-coverage-account-timeline-account-a")).toBeInTheDocument();
    expect(screen.getByTestId("weekly-coverage-account-timeline-account-b")).toBeInTheDocument();
    expect(screen.getAllByTestId("weekly-coverage-axis")).toHaveLength(1);
    expectClosedDetails();
    expect(screen.queryByRole("button", { name: /Account A/ })).not.toBeInTheDocument();
  });

  it("gives each modeled timeline an accessible date description", async () => {
    const user = userEvent.setup();
    renderWithProviders(<WeeklyCoverageCard coverage={coverage()} />);

    const poolTimeline = timelineFor("weekly-coverage-pool-timeline");
    const accountTimeline = timelineFor("weekly-coverage-account-timeline-account-a");

    expect(poolTimeline).toHaveAttribute("role", "img");
    expect(poolTimeline).toHaveAttribute("aria-label", expect.stringContaining("Jan 1"));
    expect(poolTimeline).toHaveAttribute("aria-label", expect.stringContaining("Jan 8"));
    expect(accountTimeline).toHaveAttribute("role", "img");
    expect(accountTimeline).toHaveAttribute("aria-label", expect.stringContaining("Jan 1"));
    expect(accountTimeline).toHaveAttribute("aria-label", expect.stringContaining("Jan 8"));

    await user.click(screen.getByTestId("weekly-coverage-horizon-14"));

    expect(screen.getByTestId("weekly-coverage-pool-timeline")).toHaveAttribute(
      "aria-label",
      expect.stringContaining("Jan 15"),
    );
  });

  it("calls out an immediately empty ready pool without adding another panel", () => {
    renderWithProviders(
      <WeeklyCoverageCard
        coverage={coverage({
          intervals: [interval(GENERATED_AT, HORIZON_AT, "exhausted")],
        })}
      />,
    );

    expect(screen.getByText("Weekly pool is empty now")).toBeInTheDocument();
    expect(screen.getByTestId("weekly-coverage-pool-timeline")).toBeInTheDocument();
    expectClosedDetails();
  });

  it("keeps a limited account pace independent and ends it at the current reset", () => {
    renderWithProviders(
      <WeeklyCoverageCard
        coverage={coverage({
          status: "limited",
          accounts: [account({
            status: "limited",
            reason: "insufficient_calibration",
            remainingPercent: 61,
            quotaPaceStatus: "exhausts_before_reset",
            usedPercentPerDay: 10.5,
            projectedExhaustionAt: "2026-01-06T12:00:00.000Z",
            projectedRemainingAtReset: 0,
            intervals: [],
          })],
          intervals: [],
          minimumReserveHours: null,
          minimumReserveAt: null,
        })}
      />,
    );

    const timeline = timelineFor("weekly-coverage-account-timeline-account-a");
    const description = timeline.getAttribute("aria-label") ?? "";
    expect(description).toContain("Jan 8");
    const available = timeline.querySelector('[data-state="available"]');
    const exhausted = timeline.querySelector('[data-state="exhausted"]');
    expect(available).toHaveStyle({ width: "71.42857142857143%" });
    expect(exhausted).toHaveStyle({ width: "28.57142857142857%" });
    expectClosedDetails();
  });

  it("labels a zero-usage account without presenting a paced reserve", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <WeeklyCoverageCard
        coverage={coverage({
          status: "limited",
          accounts: [account({
            status: "limited",
            reason: "insufficient_calibration",
            quotaPaceStatus: "no_usage",
            usedPercentPerDay: 0,
            projectedRemainingAtReset: 100,
            intervals: [],
          })],
          intervals: [],
          minimumReserveHours: null,
          minimumReserveAt: null,
        })}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Details" }));

    const details = screen.getByTestId("weekly-coverage-details");
    expect(details).toHaveTextContent("No usage observed in this window");
    expect(details).not.toHaveTextContent("100% at reset");
  });

  it("uses an unknown timeline for stale accounts without a green segment", () => {
    renderWithProviders(
      <WeeklyCoverageCard
        coverage={coverage({
          status: "limited",
          accounts: [account({
            status: "limited",
            reason: "stale_usage",
            remainingPercent: 83,
            quotaPaceStatus: "unavailable",
            usedPercentPerDay: null,
            projectedRemainingAtReset: null,
            intervals: [],
          })],
          intervals: [],
          minimumReserveHours: null,
          minimumReserveAt: null,
        })}
      />,
    );

    const timeline = timelineFor("weekly-coverage-account-timeline-account-a");
    const poolTimeline = timelineFor("weekly-coverage-pool-timeline");
    expect(timeline).toHaveAttribute("role", "img");
    expect(timeline.querySelector('[data-state="available"]')).toBeNull();
    expect(poolTimeline.querySelector('[data-state="available"]')).toBeNull();
  });

  it("keeps excluded accounts out of the chart until Details is opened", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <WeeklyCoverageCard
        coverage={coverage({
          accounts: [
            account(),
            account({
              accountId: "account-paused",
              label: "Paused account",
              status: "excluded",
              reason: "paused",
              remainingPercent: null,
              resetAt: null,
              capacityWorkUnits: null,
              sampleCount: 0,
              observedDropPercent: 0,
              intervals: [],
              quotaPaceStatus: "unavailable",
              usedPercentPerDay: null,
              projectedRemainingAtReset: null,
            }),
          ],
        })}
      />,
    );

    expect(screen.queryByTestId("weekly-coverage-account-timeline-account-paused")).not.toBeInTheDocument();
    expect(screen.queryByTestId("weekly-coverage-account-timeline-unavailable-account-paused")).not.toBeInTheDocument();
    expectClosedDetails();

    await user.click(screen.getByRole("button", { name: "Details" }));

    expect(screen.getByTestId("weekly-coverage-details")).toBeVisible();
    expect(screen.getByTestId("weekly-coverage-account-evidence-account-paused")).toHaveTextContent("Paused account");
    expect(screen.getByTestId("weekly-coverage-excluded-summary")).toHaveTextContent(
      "1 account excluded from the forecast",
    );
  });

  it("moves evidence and reserve explanation into the shared Details disclosure", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <WeeklyCoverageCard
        coverage={coverage({
          warnings: ["incomplete_evidence"],
          accounts: [account({
            diagnostics: {
              discardedIntervalCount: 2,
              unpricedModels: ["codex-auto-review"],
            },
          })],
        })}
      />,
    );

    expect(screen.queryByText(/Tightest projected reserve/)).not.toBeInTheDocument();
    expect(screen.queryByText(/codex-auto-review/)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Details" }));

    expect(screen.getByTestId("weekly-coverage-details")).toHaveTextContent("Tightest projected reserve");
    expect(screen.getByTestId("weekly-coverage-account-evidence-account-a")).toHaveTextContent(
      "codex-auto-review",
    );
  });

  it("keeps the seven and fourteen day horizon controls and later-gap hint", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <WeeklyCoverageCard
        coverage={coverage({
          intervals: [
            interval(GENERATED_AT, "2026-01-11T12:00:00.000Z", "available"),
            interval("2026-01-11T12:00:00.000Z", "2026-01-12T12:00:00.000Z", "exhausted"),
            interval("2026-01-12T12:00:00.000Z", HORIZON_AT, "available"),
          ],
        })}
      />,
    );

    expect(screen.getByTestId("weekly-coverage-horizon-7")).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByTestId("weekly-coverage-gap-beyond-default")).toHaveTextContent(
      "begins after the 7-day view",
    );

    await user.click(screen.getByTestId("weekly-coverage-horizon-14"));

    expect(screen.getByTestId("weekly-coverage-horizon-14")).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByTestId("weekly-coverage-horizon-7")).toHaveAttribute("aria-pressed", "false");
    expect(screen.queryByTestId("weekly-coverage-gap-beyond-default")).not.toBeInTheDocument();
  });
});
