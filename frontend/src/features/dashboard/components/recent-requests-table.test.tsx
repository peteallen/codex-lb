import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useAuthStore } from "@/features/auth/hooks/use-auth";
import { RecentRequestsTable } from "@/features/dashboard/components/recent-requests-table";
import { RequestLogSchema } from "@/features/dashboard/schemas";
import { formatDateTimeLines } from "@/utils/formatters";
import { useDateDisplayFormatStore } from "@/hooks/use-date-format";

const ISO = "2026-01-01T12:00:00+00:00";
const NULL_FAILURE_METADATA = {
  failurePhase: null,
  failureDetail: null,
  failureExceptionType: null,
  upstreamStatusCode: null,
  upstreamErrorCode: null,
  bridgeStage: null,
};
const NULL_USERAGENT_METADATA = {
  useragent: null,
  useragentGroup: null,
  clientIp: null,
};
const NULL_LATENCY_METADATA = {
  latencyFirstUpstreamEventMs: null,
  latencyResponseCreatedMs: null,
};

const { toastSuccess, toastError } = vi.hoisted(() => ({
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));
const originalClipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
const originalIsSecureContext = Object.getOwnPropertyDescriptor(window, "isSecureContext");

vi.mock("sonner", () => ({
  toast: {
    success: toastSuccess,
    error: toastError,
  },
}));

vi.mock("@/features/conversation-archive/components/request-archive-panel", () => ({
  RequestArchivePanel: ({ requestId }: { requestId: string }) => (
    <div data-testid="request-archive-panel">Archive for {requestId}</div>
  ),
}));

const PAGINATION_PROPS = {
  total: 1,
  limit: 25,
  offset: 0,
  hasMore: false,
  onLimitChange: vi.fn(),
  onOffsetChange: vi.fn(),
};

function openRequestDetails() {
  fireEvent.click(screen.getByRole("button", { name: "View Details" }));
  return screen.getByRole("dialog");
}

describe("RecentRequestsTable", () => {
  beforeEach(() => {
    toastSuccess.mockReset();
    toastError.mockReset();
    useAuthStore.setState({
      role: "admin",
      permissions: ["read", "write"],
      canWrite: true,
    });
  });

  afterEach(() => {
    if (originalClipboard) {
      Object.defineProperty(navigator, "clipboard", originalClipboard);
    }

    if (originalIsSecureContext) {
      Object.defineProperty(window, "isSecureContext", originalIsSecureContext);
    }
  });

  it("preserves exact attempt rows and API order when shared request IDs refresh or leave the page", () => {
    const attempt = (logId: string, requestId: string, accountId: string | null, requestedAt: string) =>
      RequestLogSchema.parse({
        logId,
        requestId,
        accountId,
        requestedAt,
        model: "gpt-6-sol",
        status: "error",
        errorCode: "model_not_found",
        errorMessage: logId,
        tokens: null,
        cachedInputTokens: null,
        reasoningEffort: null,
        costUsd: null,
        latencyMs: null,
      });
    const initial = [
      attempt("4", "req-b", "openai5", "2026-09-23T03:37:53.909368Z"),
      attempt("3", "req-b", "openai6", "2026-09-23T03:37:52.959694Z"),
      attempt("2", "req-a", "openai5", "2026-09-23T03:37:50.877645Z"),
      attempt("1", "req-a", "openai6", "2026-09-23T03:37:50.037085Z"),
    ];
    const refreshed = [
      attempt("6", "req-c", "openai5", "2026-09-23T03:38:02.396128Z"),
      attempt("5", "req-c", "openai6", "2026-09-23T03:38:01.582212Z"),
      ...initial.slice(0, 2),
    ];
    const sameCorrelation = [
      attempt("8", "req-d", null, ISO),
      attempt("7", "req-d", null, ISO),
    ];
    const table = (requests: typeof initial) => (
      <RecentRequestsTable {...PAGINATION_PROPS} accounts={[]} requests={requests} total={8} />
    );
    const assertRows = (requests: typeof initial) => {
      const rows = screen.getAllByRole("row").slice(1);
      expect(rows).toHaveLength(requests.length);
      rows.forEach((row, index) => {
        const request = requests[index];
        const cells = within(row).getAllByRole("cell");
        const time = formatDateTimeLines(request.requestedAt, useDateDisplayFormatStore.getState().dateDisplayFormat);
        expect(cells[0]).toHaveTextContent(time.primary);
        expect(cells[1]).toHaveTextContent(request.accountId ?? "Unassigned");
        expect(within(row).getByText(request.errorMessage!, { exact: true })).toBeInTheDocument();
      });
    };
    const { rerender } = render(table(initial));
    assertRows(initial);

    rerender(table(refreshed));
    assertRows(refreshed);

    rerender(table(initial));
    assertRows(initial);

    rerender(table(sameCorrelation));
    assertRows(sameCorrelation);

    rerender(table(sameCorrelation.slice(1)));
    assertRows(sameCorrelation.slice(1));
  });

  it("renders rows with status badges and supports request details and copy actions", async () => {
    const longError = "Rate limit reached while processing this request ".repeat(3);
    const writeText = vi.fn().mockResolvedValue(undefined);

    Object.defineProperty(window, "isSecureContext", {
      configurable: true,
      value: true,
    });
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    render(
      <RecentRequestsTable
        {...PAGINATION_PROPS}
         accounts={[
           {
             accountId: "acc-primary",
             email: "primary@example.com",
             displayName: "Primary Account",
             planType: "plus",
             status: "active",
             limitWarmupEnabled: false,
             additionalQuotas: [],
           },
         ]}
        requests={[
          {
            requestedAt: ISO,
            accountId: "acc-primary",
            planType: "plus",
            apiKeyName: "Key Alpha",
            apiKeyId: "key-alpha",
            logId: "req-1",
            requestId: "req-1",
            conversationId: null,
            archiveRequestId: "archive-req-1",
            requestKind: "normal",
            model: "gpt-5.1",
            source: null,
            serviceTier: "default",
            requestedServiceTier: "priority",
            actualServiceTier: "default",
            transport: "websocket",
             status: "rate_limit",
             errorCode: "rate_limit_exceeded",
             errorMessage: longError,
            ...NULL_FAILURE_METADATA,
            ...NULL_USERAGENT_METADATA,
            upstreamTransport: "auto",
             tokens: 1200,
             inputTokens: 1000,
             outputTokens: 200,
             outputTokensRaw: null,
             ...NULL_LATENCY_METADATA,
             latencyFirstTokenMs: null,
            latencyQueueMs: null,
             cachedInputTokens: 200,
             reasoningEffort: "high",
             costUsd: 0.01,
             costBreakdown: {
               inputUsd: 0.004,
               cachedInputUsd: 0.001,
               outputUsd: 0.005,
               totalUsd: 0.01,
             },
             latencyMs: 1000,
           },
         ]}
       />,
    );

    expect(screen.getByText("Primary Account")).toBeInTheDocument();
    expect(screen.getByText("Plus")).toBeInTheDocument();
    expect(screen.getByText("Key Alpha")).toBeInTheDocument();
    expect(screen.getByText("gpt-5.1 (high, default)")).toBeInTheDocument();
    expect(screen.getByText("Requested priority")).toBeInTheDocument();
    expect(screen.getByText("WS")).toBeInTheDocument();
    expect(screen.getByText("Up Auto")).toBeInTheDocument();
    expect(screen.getByText("Rate limit")).toBeInTheDocument();
    expect(screen.getByText("rate_limit_exceeded")).toBeInTheDocument();
    expect(screen.getByText(/Input: 1K.*Output: 200/)).toBeInTheDocument();
    expect(screen.getByRole("table")).toHaveClass("dashboard-request-table");
    expect(screen.getByText(/Input: 1K.*Output: 200/).closest("td")).toHaveClass("dashboard-table-tokens");
    expect(screen.getByText(/Input: 1K.*Output: 200/).closest("td")).toHaveAttribute("data-mobile-label", "Tokens");
    expect(Array.from(screen.getByRole("row", { name: /gpt-5.1/ }).querySelectorAll(".dashboard-mobile-label"), (label) => label.textContent)).toEqual([
      "Time",
      "Account",
      "API Key",
      "Model",
      "Status",
      "TTFT / TPS",
      "Tokens",
      "Cost",
      "Details",
    ]);

    const dialog = openRequestDetails();
    expect(dialog).toBeInTheDocument();
    expect(within(dialog).getByText("Request Details")).toBeInTheDocument();
    expect(within(dialog).getByText("req-1")).toBeInTheDocument();
    expect(within(dialog).getByTestId("request-archive-panel")).toHaveTextContent("Archive for archive-req-1");
    expect(within(dialog).getByText("rate_limit_exceeded")).toBeInTheDocument();
    expect(dialog.textContent).toContain("Rate limit reached while processing this request");
    expect(within(dialog).getByText("1.0 s")).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Copy Request ID" }));
      await Promise.resolve();
    });

    expect(writeText).toHaveBeenCalledWith("req-1");
    expect(toastSuccess).toHaveBeenCalledWith("Copied to clipboard");
    expect(screen.getByRole("button", { name: "Copy Request ID Copied" })).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Copy Error" }));
      await Promise.resolve();
    });

    expect(writeText).toHaveBeenCalledWith(longError);
  });

  it("shows TTFT and total-output-token TPS beside tokens", () => {
    render(
      <RecentRequestsTable
        {...PAGINATION_PROPS}
        accounts={[]}
        requests={[
          {
            requestedAt: ISO,
            accountId: "acc-speed",
            planType: "plus",
            apiKeyName: "Key Speed",
            apiKeyId: "key-speed",
            logId: "req-speed",
            requestId: "req-speed",
            conversationId: null,
            requestKind: "normal",
            model: "gpt-5.1",
            source: null,
            serviceTier: null,
            requestedServiceTier: null,
            actualServiceTier: null,
            transport: "http",
            ...NULL_USERAGENT_METADATA,
            status: "ok",
            errorCode: null,
            errorMessage: null,
            ...NULL_FAILURE_METADATA,
            tokens: 1200,
            inputTokens: 1000,
            outputTokens: 200,
            outputTokensRaw: 200,
            reasoningTokens: 40,
            cachedInputTokens: 0,
            reasoningEffort: null,
            costUsd: 0,
            costBreakdown: null,
            latencyMs: 1000,
            ...NULL_LATENCY_METADATA,
            latencyFirstUpstreamEventMs: 50,
            latencyResponseCreatedMs: 100,
            latencyFirstTokenMs: 200,
            latencyQueueMs: null,
          },
        ]}
      />,
    );

    const row = screen.getByText("gpt-5.1").closest("tr");

    expect(row).not.toBeNull();
    expect(within(row as HTMLElement).getByText("200ms")).toBeInTheDocument();
    expect(within(row as HTMLElement).getByText("250.0")).toBeInTheDocument();
  });

  it("falls back to first-output timing when a turn emits no visible token", () => {
    render(
      <RecentRequestsTable
        {...PAGINATION_PROPS}
        accounts={[]}
        requests={[
          {
            requestedAt: ISO,
            accountId: "acc-toolonly",
            planType: "plus",
            apiKeyName: "Key Speed",
            apiKeyId: "key-speed",
            logId: "req-toolonly",
            requestId: "req-toolonly",
            conversationId: null,
            requestKind: "normal",
            model: "gpt-5.6-sol",
            source: null,
            serviceTier: null,
            requestedServiceTier: null,
            actualServiceTier: null,
            transport: "http",
            ...NULL_USERAGENT_METADATA,
            status: "ok",
            errorCode: null,
            errorMessage: null,
            ...NULL_FAILURE_METADATA,
            tokens: 1200,
            inputTokens: 1000,
            outputTokens: 200,
            outputTokensRaw: 200,
            reasoningTokens: 40,
            cachedInputTokens: 0,
            reasoningEffort: null,
            costUsd: 0,
            costBreakdown: null,
            latencyMs: 1000,
            ...NULL_LATENCY_METADATA,
            latencyFirstTokenMs: null,
            latencyFirstUpstreamEventMs: 100,
            latencyResponseCreatedMs: 200,
            latencyQueueMs: null,
          },
        ]}
      />,
    );

    const row = screen.getByText("gpt-5.6-sol").closest("tr");

    expect(row).not.toBeNull();
    expect(within(row as HTMLElement).getByText("~200ms")).toHaveAttribute(
      "title",
      "No client-visible token in this turn; showing time to first output instead.",
    );
    expect(within(row as HTMLElement).getByText("250.0")).toBeInTheDocument();
  });

  it("does not treat transport-level upstream activity as first output", () => {
    render(
      <RecentRequestsTable
        {...PAGINATION_PROPS}
        accounts={[]}
        requests={[
          {
            requestedAt: ISO,
            accountId: "acc-upstream-only",
            planType: "plus",
            apiKeyName: "Key Speed",
            apiKeyId: "key-speed",
            logId: "req-upstream-only",
            requestId: "req-upstream-only",
            conversationId: null,
            requestKind: "normal",
            model: "gpt-5.6-upstream-only",
            source: null,
            serviceTier: null,
            requestedServiceTier: null,
            actualServiceTier: null,
            transport: "http",
            ...NULL_USERAGENT_METADATA,
            status: "ok",
            errorCode: null,
            errorMessage: null,
            ...NULL_FAILURE_METADATA,
            tokens: 1200,
            inputTokens: 1000,
            outputTokens: 200,
            outputTokensRaw: 200,
            reasoningTokens: 40,
            cachedInputTokens: 0,
            reasoningEffort: null,
            costUsd: 0,
            costBreakdown: null,
            latencyMs: 1000,
            ...NULL_LATENCY_METADATA,
            latencyFirstTokenMs: null,
            latencyFirstUpstreamEventMs: 100,
            latencyQueueMs: null,
          },
        ]}
      />,
    );

    const row = screen.getByText("gpt-5.6-upstream-only").closest("tr");

    expect(row).not.toBeNull();
    expect(within(row as HTMLElement).queryByText("~100ms")).not.toBeInTheDocument();
    expect(within(row as HTMLElement).queryByText("222.2")).not.toBeInTheDocument();
  });

  it("does not calculate TPS from fallback output tokens", () => {
    render(
      <RecentRequestsTable
        {...PAGINATION_PROPS}
        accounts={[]}
        requests={[
          {
            requestedAt: ISO,
            accountId: "acc-reasoning",
            planType: "plus",
            apiKeyName: "Key Reasoning",
            apiKeyId: "key-reasoning",
            logId: "req-reasoning",
            requestId: "req-reasoning",
            conversationId: null,
            requestKind: "normal",
            model: "gpt-5.1",
            source: null,
            serviceTier: null,
            requestedServiceTier: null,
            actualServiceTier: null,
            transport: "http",
            ...NULL_USERAGENT_METADATA,
            status: "ok",
            errorCode: null,
            errorMessage: null,
            ...NULL_FAILURE_METADATA,
            tokens: 1200,
            inputTokens: 1000,
            outputTokens: 200,
            outputTokensRaw: null,
            cachedInputTokens: 0,
            reasoningEffort: null,
            costUsd: 0,
            costBreakdown: null,
            latencyMs: 1000,
            ...NULL_LATENCY_METADATA,
            latencyFirstTokenMs: 200,
            latencyQueueMs: null,
          },
        ]}
      />,
    );

    const row = screen.getByText("gpt-5.1").closest("tr");

    expect(row).not.toBeNull();
    expect(within(row as HTMLElement).getByText("200ms")).toBeInTheDocument();
    expect(within(row as HTMLElement).getByText("--")).toBeInTheDocument();
    expect(within(row as HTMLElement).queryByText("250.0")).not.toBeInTheDocument();
  });

  it("does not show approximate first output for a zero-output row", () => {
    render(
      <RecentRequestsTable
        {...PAGINATION_PROPS}
        accounts={[]}
        requests={[
          {
            requestedAt: ISO,
            accountId: "acc-reasoning-only",
            planType: "plus",
            apiKeyName: "Key Reasoning",
            apiKeyId: "key-reasoning",
            logId: "req-reasoning-only",
            requestId: "req-reasoning-only",
            conversationId: null,
            requestKind: "normal",
            model: "gpt-5.6-reasoning-only",
            source: null,
            serviceTier: null,
            requestedServiceTier: null,
            actualServiceTier: null,
            transport: "http",
            ...NULL_USERAGENT_METADATA,
            status: "ok",
            errorCode: null,
            errorMessage: null,
            ...NULL_FAILURE_METADATA,
            tokens: 1000,
            inputTokens: 1000,
            outputTokens: 0,
            outputTokensRaw: 0,
            reasoningTokens: 200,
            cachedInputTokens: 0,
            reasoningEffort: null,
            costUsd: 0,
            costBreakdown: null,
            latencyMs: 1000,
            ...NULL_LATENCY_METADATA,
            latencyFirstTokenMs: null,
            latencyResponseCreatedMs: 200,
            latencyQueueMs: null,
          },
        ]}
      />,
    );

    const row = screen.getByText("gpt-5.6-reasoning-only").closest("tr");

    expect(row).not.toBeNull();
    expect(within(row as HTMLElement).queryByText("~200ms")).not.toBeInTheDocument();
    expect(within(row as HTMLElement).queryByText("250.0")).not.toBeInTheDocument();
  });

  it("renders empty state", () => {
    render(<RecentRequestsTable {...PAGINATION_PROPS} total={0} accounts={[]} requests={[]} />);
    expect(screen.getByText("No request logs match the current filters.")).toBeInTheDocument();
  });

  it("hides identifying metadata and archive controls from guests", () => {
    useAuthStore.setState({
      role: "guest",
      permissions: ["read"],
      canWrite: false,
    });

    render(
      <RecentRequestsTable
        {...PAGINATION_PROPS}
        accounts={[]}
        requests={[
          {
            requestedAt: ISO,
            accountId: null,
            planType: null,
            apiKeyName: null,
            apiKeyId: null,
            logId: "req-guest",
            requestId: "req-guest",
            archiveRequestId: null,
            conversationId: null,
            requestKind: "normal",
            model: "gpt-5.1",
            source: null,
            serviceTier: null,
            requestedServiceTier: null,
            actualServiceTier: null,
            transport: "http",
            useragent: null,
            useragentGroup: "codex-cli",
            clientIp: null,
            status: "ok",
            errorCode: null,
            errorMessage: null,
            ...NULL_FAILURE_METADATA,
            tokens: 120,
            inputTokens: 100,
            outputTokens: 20,
            outputTokensRaw: 20,
            ...NULL_LATENCY_METADATA,
            latencyFirstTokenMs: 50,
            latencyQueueMs: null,
            cachedInputTokens: 0,
            reasoningEffort: null,
            costUsd: 0.01,
            costBreakdown: null,
            latencyMs: 250,
          },
        ]}
      />,
    );

    const dialog = openRequestDetails();

    expect(within(dialog).getByText("req-guest")).toBeInTheDocument();
    expect(within(dialog).getByText("gpt-5.1")).toBeInTheDocument();
    expect(within(dialog).queryByText("User Agent")).not.toBeInTheDocument();
    expect(within(dialog).queryByText("Client IP")).not.toBeInTheDocument();
    expect(within(dialog).queryByText("Conversation ID")).not.toBeInTheDocument();
    expect(within(dialog).queryByTestId("request-archive-panel")).not.toBeInTheDocument();
  });

  it("shows warmup marker only for warmup rows", () => {
    render(
      <RecentRequestsTable
        {...PAGINATION_PROPS}
        total={2}
        hasMore
        accounts={[]}
        requests={[
          {
            requestedAt: ISO,
            accountId: "acc-normal",
            planType: null,
            apiKeyName: null,
            apiKeyId: null,
            logId: "req-normal",
            requestId: "req-normal",
            conversationId: null,
            requestKind: "normal",
            source: null,
            ...NULL_FAILURE_METADATA,
            model: "gpt-5.1",
            serviceTier: null,
            requestedServiceTier: null,
            actualServiceTier: null,
            transport: "http",
            ...NULL_USERAGENT_METADATA,
            status: "ok",
            errorCode: null,
            errorMessage: null,
            tokens: 1,
            inputTokens: 1,
            outputTokens: 0,
            outputTokensRaw: null,
            ...NULL_LATENCY_METADATA,
            latencyFirstTokenMs: null,
            latencyQueueMs: null,
            cachedInputTokens: null,
            reasoningEffort: null,
            costUsd: 0,
            costBreakdown: null,
            latencyMs: 1,
          },
          {
            requestedAt: ISO,
            accountId: "acc-warmup",
            planType: null,
            apiKeyName: null,
            apiKeyId: null,
            logId: "req-warmup",
            requestId: "req-warmup",
            conversationId: null,
            requestKind: "warmup",
            source: null,
            ...NULL_FAILURE_METADATA,
            model: "gpt-5.1",
            serviceTier: null,
            requestedServiceTier: null,
            actualServiceTier: null,
            transport: "http",
            ...NULL_USERAGENT_METADATA,
             status: "ok",
             errorCode: null,
             errorMessage: null,
            tokens: 1,
            inputTokens: 1,
            outputTokens: 0,
            outputTokensRaw: null,
            ...NULL_LATENCY_METADATA,
            latencyFirstTokenMs: null,
            latencyQueueMs: null,
            cachedInputTokens: null,
            reasoningEffort: null,
            costUsd: 0,
            costBreakdown: null,
            latencyMs: 1,
          },
        ]}
      />,
    );

    expect(screen.getByText("Warmup")).toBeInTheDocument();
    expect(screen.queryByText("Normal")).not.toBeInTheDocument();
  });

  it("renders placeholder transport for legacy rows", () => {
    render(
      <RecentRequestsTable
        {...PAGINATION_PROPS}
        accounts={[]}
        requests={[
          {
            requestedAt: ISO,
            accountId: "acc-legacy",
            planType: null,
            apiKeyName: null,
            apiKeyId: null,
            logId: "req-legacy",
            requestId: "req-legacy",
            conversationId: null,
            requestKind: "normal",
            model: "gpt-5.1",
            source: null,
            serviceTier: null,
            requestedServiceTier: null,
            actualServiceTier: null,
            transport: null,
            ...NULL_USERAGENT_METADATA,
             status: "ok",
             errorCode: null,
             errorMessage: null,
            ...NULL_FAILURE_METADATA,
             tokens: 1,
             inputTokens: 1,
             outputTokens: 0,
             outputTokensRaw: null,
             ...NULL_LATENCY_METADATA,
             latencyFirstTokenMs: null,
            latencyQueueMs: null,
             cachedInputTokens: null,
             reasoningEffort: null,
             costUsd: 0,
             costBreakdown: null,
             latencyMs: 1,
           },
         ]}
       />,
    );

    const row = screen.getByText("gpt-5.1").closest("tr");
    expect(row).not.toBeNull();
    expect(within(row as HTMLElement).getAllByText("--").length).toBeGreaterThan(0);
  });

  it("shows details action for error-code-only rows", async () => {
    render(
      <RecentRequestsTable
        {...PAGINATION_PROPS}
        accounts={[]}
        requests={[
          {
            requestedAt: ISO,
            accountId: "acc-legacy",
            planType: null,
            apiKeyName: null,
            apiKeyId: null,
            logId: "req-error-code",
            requestId: "req-error-code",
            conversationId: null,
            requestKind: "normal",
            model: "gpt-5.1",
            source: null,
            serviceTier: null,
            requestedServiceTier: null,
            actualServiceTier: null,
            transport: "http",
            ...NULL_USERAGENT_METADATA,
             status: "error",
             errorCode: "upstream_error",
             errorMessage: null,
            ...NULL_FAILURE_METADATA,
             tokens: 1,
             inputTokens: 1,
             outputTokens: 0,
             outputTokensRaw: null,
             ...NULL_LATENCY_METADATA,
             latencyFirstTokenMs: null,
            latencyQueueMs: null,
             cachedInputTokens: null,
             reasoningEffort: null,
             costUsd: 0,
             costBreakdown: null,
             latencyMs: 1,
           },
         ]}
       />,
    );

    const dialog = openRequestDetails();

    expect(dialog).toHaveTextContent("upstream_error");
    expect(dialog).toHaveTextContent("Full Error");
  });

  it("shows a cost section for ok rows", () => {
    render(
      <RecentRequestsTable
        {...PAGINATION_PROPS}
        accounts={[]}
        requests={[
          {
            requestedAt: ISO,
            accountId: "acc-cost",
            planType: "plus",
            apiKeyName: "Key Cost",
            apiKeyId: "key-cost",
            logId: "req-cost",
            requestId: "req-cost",
            conversationId: null,
            requestKind: "normal",
            model: "gpt-5.1",
            source: null,
            serviceTier: null,
            requestedServiceTier: null,
            actualServiceTier: null,
            transport: "http",
            ...NULL_USERAGENT_METADATA,
            status: "ok",
            errorCode: null,
            errorMessage: null,
            ...NULL_FAILURE_METADATA,
            tokens: 1400,
            inputTokens: 1000,
            outputTokens: 400,
            outputTokensRaw: null,
            ...NULL_LATENCY_METADATA,
            latencyFirstTokenMs: null,
            latencyQueueMs: null,
            cachedInputTokens: 200,
            reasoningEffort: null,
            costUsd: 0.01,
            costBreakdown: {
              inputUsd: 0.004,
              cachedInputUsd: 0.002,
              outputUsd: 0.004,
              totalUsd: 0.01,
            },
            latencyMs: 100,
          },
        ]}
      />,
    );

    const dialog = openRequestDetails();
    const costSection = within(dialog).getByText("Cost").closest("div.space-y-2");

    expect(within(dialog).getByText("Cost")).toBeInTheDocument();
    expect(costSection).toHaveTextContent("$0.01 =");
    expect(costSection).toHaveTextContent("800 Input ($0.00)");
    expect(costSection).toHaveTextContent("200 Cached ($0.00)");
    expect(costSection).toHaveTextContent("400 Output ($0.00)");
  });

  it("shows the full user agent in request details when present", () => {
    render(
      <RecentRequestsTable
        {...PAGINATION_PROPS}
        accounts={[]}
        requests={[
          {
            requestedAt: ISO,
            accountId: "acc-useragent",
            planType: "plus",
            apiKeyName: "Key Agent",
            apiKeyId: "key-agent",
            logId: "req-useragent",
            requestId: "req-useragent",
            conversationId: null,
            requestKind: "normal",
            model: "gpt-5.1",
            source: null,
            serviceTier: null,
            requestedServiceTier: null,
            actualServiceTier: null,
            transport: "http",
            useragent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36",
            useragentGroup: "Mozilla",
            clientIp: "203.0.113.7",
            status: "ok",
            errorCode: null,
            errorMessage: null,
            ...NULL_FAILURE_METADATA,
            tokens: 1,
            inputTokens: 1,
            outputTokens: 0,
            outputTokensRaw: null,
            ...NULL_LATENCY_METADATA,
            latencyFirstTokenMs: null,
            latencyQueueMs: null,
            cachedInputTokens: null,
            reasoningEffort: null,
            costUsd: 0,
            costBreakdown: null,
            latencyMs: 1,
          },
        ]}
      />,
    );

    const dialog = openRequestDetails();
    const dialogText = dialog.textContent ?? "";
    const errorCodeIndex = dialogText.indexOf("Error Code");
    const userAgentIndex = dialogText.indexOf("User Agent");
    const clientIpIndex = dialogText.indexOf("Client IP");

    expect(within(dialog).getByText("User Agent")).toBeInTheDocument();
    expect(
      within(dialog).getByText("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36"),
    ).toBeInTheDocument();
    expect(within(dialog).getByText("Client IP")).toBeInTheDocument();
    expect(within(dialog).getByText("203.0.113.7")).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Copy User Agent" })).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Copy Client IP" })).toBeInTheDocument();
    expect(errorCodeIndex).toBeGreaterThanOrEqual(0);
    expect(userAgentIndex).toBeGreaterThan(errorCodeIndex);
    expect(clientIpIndex).toBeGreaterThan(userAgentIndex);
  });

  it("shows an em dash for missing user agent in request details", () => {
    render(
      <RecentRequestsTable
        {...PAGINATION_PROPS}
        accounts={[]}
        requests={[
          {
            requestedAt: ISO,
            accountId: "acc-no-useragent",
            planType: null,
            apiKeyName: null,
            apiKeyId: null,
            logId: "req-no-useragent",
            requestId: "req-no-useragent",
            conversationId: null,
            requestKind: "normal",
            model: "gpt-5.1",
            source: null,
            serviceTier: null,
            requestedServiceTier: null,
            actualServiceTier: null,
            transport: "http",
            useragent: null,
            useragentGroup: null,
            clientIp: null,
            status: "ok",
            errorCode: null,
            errorMessage: null,
            ...NULL_FAILURE_METADATA,
            tokens: 1,
            inputTokens: 1,
            outputTokens: 0,
            outputTokensRaw: null,
            ...NULL_LATENCY_METADATA,
            latencyFirstTokenMs: null,
            latencyQueueMs: null,
            cachedInputTokens: null,
            reasoningEffort: null,
            costUsd: 0,
            costBreakdown: null,
            latencyMs: 1,
          },
        ]}
      />,
    );

    const dialog = openRequestDetails();
    const userAgentField = within(dialog).getByText("User Agent").closest("div.space-y-1");
    const clientIpField = within(dialog).getByText("Client IP").closest("div.space-y-1");

    expect(userAgentField).not.toBeNull();
    expect(userAgentField).toHaveTextContent("User Agent");
    expect(userAgentField).toHaveTextContent("—");
    expect(clientIpField).not.toBeNull();
    expect(clientIpField).toHaveTextContent("Client IP");
    expect(clientIpField).toHaveTextContent("—");
    expect(within(dialog).queryByRole("button", { name: "Copy" })).not.toBeInTheDocument();
  });

  it("hides the cost section for non-ok rows", () => {
    render(
      <RecentRequestsTable
        {...PAGINATION_PROPS}
        accounts={[]}
        requests={[
          {
            requestedAt: ISO,
            accountId: "acc-no-cost",
            planType: null,
            apiKeyName: null,
            apiKeyId: null,
            logId: "req-no-cost",
            requestId: "req-no-cost",
            conversationId: null,
            requestKind: "normal",
            model: "gpt-5.1",
            source: null,
            serviceTier: null,
            requestedServiceTier: null,
            actualServiceTier: null,
            transport: "http",
            ...NULL_USERAGENT_METADATA,
            status: "error",
            errorCode: "upstream_error",
            errorMessage: "boom",
            ...NULL_FAILURE_METADATA,
            tokens: 1,
            inputTokens: 1,
            outputTokens: 0,
            outputTokensRaw: null,
            ...NULL_LATENCY_METADATA,
            latencyFirstTokenMs: null,
            latencyQueueMs: null,
            cachedInputTokens: 0,
            reasoningEffort: null,
            costUsd: 0.01,
            costBreakdown: {
              inputUsd: 0.01,
              cachedInputUsd: null,
              outputUsd: null,
              totalUsd: 0.01,
            },
            latencyMs: 1,
          },
        ]}
      />,
    );

    const dialog = openRequestDetails();

    expect(within(dialog).queryByText("Cost")).not.toBeInTheDocument();
  });

  it("renders only available cost segments for partial data", () => {
    render(
      <RecentRequestsTable
        {...PAGINATION_PROPS}
        accounts={[]}
        requests={[
          {
            requestedAt: ISO,
            accountId: "acc-partial-cost",
            planType: "plus",
            apiKeyName: "Key Partial",
            apiKeyId: "key-partial",
            logId: "req-partial-cost",
            requestId: "req-partial-cost",
            conversationId: null,
            requestKind: "normal",
            model: "gpt-5.1",
            source: null,
            serviceTier: null,
            requestedServiceTier: null,
            actualServiceTier: null,
            transport: "http",
            ...NULL_USERAGENT_METADATA,
            status: "ok",
            errorCode: null,
            errorMessage: null,
            ...NULL_FAILURE_METADATA,
            tokens: 700,
            inputTokens: 700,
            outputTokens: null,
            outputTokensRaw: null,
            ...NULL_LATENCY_METADATA,
            latencyFirstTokenMs: null,
            latencyQueueMs: null,
            cachedInputTokens: 200,
            reasoningEffort: null,
            costUsd: 0.01,
            costBreakdown: {
              inputUsd: 0.006,
              cachedInputUsd: 0.004,
              outputUsd: null,
              totalUsd: 0.01,
            },
            latencyMs: 1,
          },
        ]}
      />,
    );

    const dialog = openRequestDetails();
    const costSection = within(dialog).getByText("Cost").closest("div.space-y-2");

    expect(within(dialog).getByText("Cost")).toBeInTheDocument();
    expect(costSection).toHaveTextContent("$0.01 =");
    expect(costSection).toHaveTextContent("500 Input ($0.01)");
    expect(costSection).toHaveTextContent("200 Cached ($0.00)");
    expect(costSection).not.toHaveTextContent("Output");
  });

  it("renders available cost segments when total cost is unavailable", () => {
    render(
      <RecentRequestsTable
        {...PAGINATION_PROPS}
        accounts={[]}
        requests={[
          {
            requestedAt: ISO,
            accountId: "acc-partial-no-total",
            planType: "plus",
            apiKeyName: "Key Partial No Total",
            apiKeyId: "key-partial-no-total",
            logId: "req-partial-no-total",
            requestId: "req-partial-no-total",
            conversationId: null,
            requestKind: "normal",
            model: "gpt-5.1",
            source: null,
            serviceTier: null,
            requestedServiceTier: null,
            actualServiceTier: null,
            transport: "http",
            ...NULL_USERAGENT_METADATA,
            status: "ok",
            errorCode: null,
            errorMessage: null,
            ...NULL_FAILURE_METADATA,
            tokens: null,
            inputTokens: 1000,
            outputTokens: null,
            outputTokensRaw: null,
            ...NULL_LATENCY_METADATA,
            latencyFirstTokenMs: null,
            latencyQueueMs: null,
            cachedInputTokens: 200,
            reasoningEffort: null,
            costUsd: null,
            costBreakdown: {
              inputUsd: 0.006,
              cachedInputUsd: 0.004,
              outputUsd: null,
              totalUsd: null,
            },
            latencyMs: 1,
          },
        ]}
      />,
    );

    const dialog = openRequestDetails();
    const costSection = within(dialog).getByText("Cost").closest("div.space-y-2");

    expect(within(dialog).getByText("Cost")).toBeInTheDocument();
    expect(costSection).not.toHaveTextContent("=");
    expect(costSection).toHaveTextContent("800 Input ($0.01)");
    expect(costSection).toHaveTextContent("200 Cached ($0.00)");
    expect(costSection).not.toHaveTextContent("Output");
  });

  it("shows the full user agent in request details when present", () => {
    render(
      <RecentRequestsTable
        {...PAGINATION_PROPS}
        accounts={[]}
        requests={[
          {
            requestedAt: ISO,
            accountId: "acc-useragent",
            planType: "plus",
            apiKeyName: "Key Agent",
            apiKeyId: "key-agent",
            logId: "req-useragent",
            requestId: "req-useragent",
            conversationId: null,
            requestKind: "normal",
            model: "gpt-5.1",
            source: null,
            serviceTier: null,
            requestedServiceTier: null,
            actualServiceTier: null,
            transport: "http",
            useragent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36",
            useragentGroup: "Mozilla",
            clientIp: "203.0.113.7",
            status: "ok",
            errorCode: null,
            errorMessage: null,
            ...NULL_FAILURE_METADATA,
            tokens: 1,
            inputTokens: 1,
            outputTokens: 0,
            outputTokensRaw: null,
            ...NULL_LATENCY_METADATA,
            latencyFirstTokenMs: null,
            latencyQueueMs: null,
            cachedInputTokens: null,
            reasoningEffort: null,
            costUsd: 0,
            costBreakdown: null,
            latencyMs: 1,
          },
        ]}
      />,
    );

    const dialog = openRequestDetails();
    const dialogText = dialog.textContent ?? "";
    const errorCodeIndex = dialogText.indexOf("Error Code");
    const userAgentIndex = dialogText.indexOf("User Agent");
    const clientIpIndex = dialogText.indexOf("Client IP");

    expect(within(dialog).getByText("User Agent")).toBeInTheDocument();
    expect(
      within(dialog).getByText("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36"),
    ).toBeInTheDocument();
    expect(within(dialog).getByText("Client IP")).toBeInTheDocument();
    expect(within(dialog).getByText("203.0.113.7")).toBeInTheDocument();
    expect(errorCodeIndex).toBeGreaterThanOrEqual(0);
    expect(userAgentIndex).toBeGreaterThan(errorCodeIndex);
    expect(clientIpIndex).toBeGreaterThan(userAgentIndex);
  });

  it("shows an em dash for missing user agent in request details", () => {
    render(
      <RecentRequestsTable
        {...PAGINATION_PROPS}
        accounts={[]}
        requests={[
          {
            requestedAt: ISO,
            accountId: "acc-no-useragent",
            planType: null,
            apiKeyName: null,
            apiKeyId: null,
            logId: "req-no-useragent",
            requestId: "req-no-useragent",
            conversationId: null,
            requestKind: "normal",
            model: "gpt-5.1",
            source: null,
            serviceTier: null,
            requestedServiceTier: null,
            actualServiceTier: null,
            transport: "http",
            useragent: null,
            useragentGroup: null,
            clientIp: null,
            status: "ok",
            errorCode: null,
            errorMessage: null,
            ...NULL_FAILURE_METADATA,
            tokens: 1,
            inputTokens: 1,
            outputTokens: 0,
            outputTokensRaw: null,
            ...NULL_LATENCY_METADATA,
            latencyFirstTokenMs: null,
            latencyQueueMs: null,
            cachedInputTokens: null,
            reasoningEffort: null,
            costUsd: 0,
            costBreakdown: null,
            latencyMs: 1,
          },
        ]}
      />,
    );

    const dialog = openRequestDetails();
    const userAgentField = within(dialog).getByText("User Agent").closest("div.space-y-1");
    const clientIpField = within(dialog).getByText("Client IP").closest("div.space-y-1");

    expect(userAgentField).not.toBeNull();
    expect(userAgentField).toHaveTextContent("User Agent");
    expect(userAgentField).toHaveTextContent("—");
    expect(clientIpField).not.toBeNull();
    expect(clientIpField).toHaveTextContent("Client IP");
    expect(clientIpField).toHaveTextContent("—");
    expect(within(dialog).getByText("1 ms")).toBeInTheDocument();
  });

  it("hides the cost section for total-only cost breakdown rows", () => {
    render(
      <RecentRequestsTable
        {...PAGINATION_PROPS}
        accounts={[]}
        requests={[
          {
            requestedAt: ISO,
            accountId: "acc-total-only-cost",
            planType: "plus",
            apiKeyName: "Key Total Only",
            apiKeyId: "key-total-only",
            logId: "req-total-only-cost",
            requestId: "req-total-only-cost",
            conversationId: null,
            requestKind: "normal",
            model: "gpt-5.1",
            source: null,
            serviceTier: null,
            requestedServiceTier: null,
            actualServiceTier: null,
            transport: "http",
            useragent: null,
            useragentGroup: null,
            clientIp: null,
            status: "ok",
            errorCode: null,
            errorMessage: null,
            ...NULL_FAILURE_METADATA,
            tokens: 1500,
            inputTokens: 1000,
            outputTokens: 500,
            outputTokensRaw: null,
            ...NULL_LATENCY_METADATA,
            latencyFirstTokenMs: null,
            latencyQueueMs: null,
            cachedInputTokens: null,
            reasoningEffort: null,
            costUsd: 4.321234,
            costBreakdown: {
              inputUsd: null,
              cachedInputUsd: null,
              outputUsd: null,
              totalUsd: 4.321234,
            },
            latencyMs: 1,
          },
        ]}
      />,
    );

    const dialog = openRequestDetails();

    expect(within(dialog).queryByText("Cost")).not.toBeInTheDocument();
  });

  it("closes the dialog when conversation ID button is clicked and fires handler", () => {
    const onConversationClick = vi.fn();
    render(
      <RecentRequestsTable
        {...PAGINATION_PROPS}
        accounts={[]}
        onConversationClick={onConversationClick}
        requests={[
          {
            requestedAt: ISO,
            accountId: "acc-conv-click",
            planType: "plus",
            apiKeyName: "Key Conv",
            apiKeyId: "key-conv",
            logId: "req-conv-click",
            requestId: "req-conv-click",
            requestKind: "normal",
            model: "gpt-5.1",
            source: null,
            serviceTier: null,
            requestedServiceTier: null,
            actualServiceTier: null,
            transport: "http",
            useragent: null,
            useragentGroup: null,
            clientIp: "10.0.0.1",
            conversationId: "conv_dialog_close_test",
            status: "ok",
            errorCode: null,
            errorMessage: null,
            ...NULL_FAILURE_METADATA,
            tokens: 1,
            inputTokens: 1,
            outputTokens: 0,
            outputTokensRaw: null,
            ...NULL_LATENCY_METADATA,
            latencyFirstTokenMs: null,
            latencyQueueMs: null,
            cachedInputTokens: null,
            reasoningEffort: null,
            costUsd: 0,
            costBreakdown: null,
            latencyMs: 1,
          },
        ]}
      />,
    );

    const dialog = openRequestDetails();
    expect(within(dialog).getByText("conv_dialog_close_test")).toBeInTheDocument();

    const convButton = within(dialog).getByRole("button", { name: /Filter by conversation/i });
    fireEvent.click(convButton);

    expect(onConversationClick).toHaveBeenCalledWith("conv_dialog_close_test");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("renders conversation ID as plain text when no handler is provided", () => {
    render(
      <RecentRequestsTable
        {...PAGINATION_PROPS}
        accounts={[]}
        requests={[
          {
            requestedAt: ISO,
            accountId: "acc-conv-text",
            planType: "plus",
            apiKeyName: "Key Text",
            apiKeyId: "key-text",
            logId: "req-conv-text",
            requestId: "req-conv-text",
            requestKind: "normal",
            model: "gpt-5.1",
            source: null,
            serviceTier: null,
            requestedServiceTier: null,
            actualServiceTier: null,
            transport: "http",
            useragent: null,
            useragentGroup: null,
            clientIp: null,
            conversationId: "conv_plain_text_render",
            status: "ok",
            errorCode: null,
            errorMessage: null,
            ...NULL_FAILURE_METADATA,
            tokens: 1,
            inputTokens: 1,
            outputTokens: 0,
            outputTokensRaw: null,
            ...NULL_LATENCY_METADATA,
            latencyFirstTokenMs: null,
            latencyQueueMs: null,
            cachedInputTokens: null,
            reasoningEffort: null,
            costUsd: 0,
            costBreakdown: null,
            latencyMs: 1,
          },
        ]}
      />,
    );

    const dialog = openRequestDetails();
    const textEl = within(dialog).getByText("conv_plain_text_render");
    expect(textEl).toBeInTheDocument();
    // Must be a <p>, not a button
    expect(textEl.tagName).toBe("P");
    expect(textEl).toHaveClass("truncate");
    expect(
      within(dialog).queryByRole("button", { name: /Filter by conversation/i }),
    ).not.toBeInTheDocument();
  });

  it("truncates long conversation IDs with title attribute in dialog", () => {
    const longId = "conv_this_is_a_very_very_very_very_long_conversation_id_that_would_overflow_a_half_width_column";
    render(
      <RecentRequestsTable
        {...PAGINATION_PROPS}
        accounts={[]}
        onConversationClick={vi.fn()}
        requests={[
          {
            requestedAt: ISO,
            accountId: "acc-long-cid",
            planType: "plus",
            apiKeyName: "Key Long",
            apiKeyId: "key-long",
            logId: "req-long-cid",
            requestId: "req-long-cid",
            requestKind: "normal",
            model: "gpt-5.1",
            source: null,
            serviceTier: null,
            requestedServiceTier: null,
            actualServiceTier: null,
            transport: "http",
            useragent: null,
            useragentGroup: null,
            clientIp: null,
            conversationId: longId,
            status: "ok",
            errorCode: null,
            errorMessage: null,
            ...NULL_FAILURE_METADATA,
            tokens: 1,
            inputTokens: 1,
            outputTokens: 0,
            outputTokensRaw: null,
            ...NULL_LATENCY_METADATA,
            latencyFirstTokenMs: null,
            latencyQueueMs: null,
            cachedInputTokens: null,
            reasoningEffort: null,
            costUsd: 0,
            costBreakdown: null,
            latencyMs: 1,
          },
        ]}
      />,
    );

    const dialog = openRequestDetails();
    const convButton = within(dialog).getByRole("button", { name: /Filter by conversation/i });
    expect(convButton).toHaveAttribute("title", longId);
    expect(convButton).toHaveClass("truncate");
    expect(convButton.className).toMatch(/max-w-\[200px\]/);
  });

  it("truncates long no-handler conversation IDs with title attribute", () => {
    const longId = "conv_this_is_a_very_very_long_id_with_no_handler_that_would_overflow";
    render(
      <RecentRequestsTable
        {...PAGINATION_PROPS}
        accounts={[]}
        requests={[
          {
            requestedAt: ISO,
            accountId: "acc-long-cid-nh",
            planType: "plus",
            apiKeyName: "Key Long NH",
            apiKeyId: "key-long-nh",
            logId: "req-long-cid-nh",
            requestId: "req-long-cid-nh",
            requestKind: "normal",
            model: "gpt-5.1",
            source: null,
            serviceTier: null,
            requestedServiceTier: null,
            actualServiceTier: null,
            transport: "http",
            useragent: null,
            useragentGroup: null,
            clientIp: null,
            conversationId: longId,
            status: "ok",
            errorCode: null,
            errorMessage: null,
            ...NULL_FAILURE_METADATA,
            tokens: 1,
            inputTokens: 1,
            outputTokens: 0,
            outputTokensRaw: null,
            ...NULL_LATENCY_METADATA,
            latencyFirstTokenMs: null,
            latencyQueueMs: null,
            cachedInputTokens: null,
            reasoningEffort: null,
            costUsd: 0,
            costBreakdown: null,
            latencyMs: 1,
          },
        ]}
      />,
    );

    const dialog = openRequestDetails();
    const textEl = within(dialog).getByText(longId);
    expect(textEl.tagName).toBe("P");
    expect(textEl).toHaveClass("truncate");
    expect(textEl).toHaveAttribute("title", longId);
  });
});
