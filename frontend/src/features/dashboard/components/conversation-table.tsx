import { Inbox } from "lucide-react";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";

import { isEmailLabel } from "@/components/blur-email";
import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { PaginationControls } from "@/features/dashboard/components/filters/pagination-controls";
import type { AccountSummary, ConversationEntry } from "@/features/dashboard/schemas";
import { useDateDisplayFormatStore } from "@/hooks/use-date-format";
import { usePrivacyStore } from "@/hooks/use-privacy";
import {
  formatCompactNumber,
  formatConversationDuration,
  formatCurrency,
  formatNumber,
  formatDateTimeLines,
} from "@/utils/formatters";

export type ConversationTableProps = {
  conversations: ConversationEntry[];
  accounts: AccountSummary[];
  total: number;
  limit: number;
  offset: number;
  hasMore: boolean;
  onLimitChange: (limit: number) => void;
  onOffsetChange: (offset: number) => void;
  onSelect: (conversationId: string) => void;
};

const headerClass = "text-[11px] font-medium uppercase tracking-wider text-muted-foreground/80";

export function ConversationTable({
  conversations,
  accounts,
  total,
  limit,
  offset,
  hasMore,
  onLimitChange,
  onOffsetChange,
  onSelect,
}: ConversationTableProps) {
  const { t } = useTranslation();
  const dateDisplayFormat = useDateDisplayFormatStore((state) => state.dateDisplayFormat);
  const blurred = usePrivacyStore((s) => s.blurred);
  const accountLabelMap = useMemo(() => {
    const labels = new Map<string, string>();
    for (const account of accounts) {
      labels.set(account.accountId, account.displayName || account.email || account.accountId);
    }
    return labels;
  }, [accounts]);

  /** Account IDs whose resolved label is an email. */
  const emailLabelIds = useMemo(() => {
    const ids = new Set<string>();
    for (const account of accounts) {
      const label = account.displayName || account.email;
      if (isEmailLabel(label, account.email)) {
        ids.add(account.accountId);
      }
    }
    return ids;
  }, [accounts]);

  const emptyState = (
    <EmptyState
      icon={Inbox}
      title={t("dashboard.conversations.emptyTitle")}
      description={t("dashboard.conversations.emptyDescription")}
    />
  );

  const paginationControls = (
    <div className="flex justify-end">
      <PaginationControls
        total={total}
        limit={limit}
        offset={offset}
        hasMore={hasMore}
        onLimitChange={onLimitChange}
        onOffsetChange={onOffsetChange}
      />
    </div>
  );

  if (conversations.length === 0) {
    if (offset === 0) {
      return emptyState;
    }

    return (
      <div className="space-y-3">
        {emptyState}
        {paginationControls}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="dashboard-conversation-table-shell rounded-xl border bg-card shadow-sm shadow-black/[0.02] dark:shadow-black/20">
        <div className="relative overflow-x-auto">
          <Table className="dashboard-conversation-table min-w-[980px] table-fixed">
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className={`w-[10%] pl-4 ${headerClass}`}>{t("dashboard.conversations.columns.lastRequest")}</TableHead>
                <TableHead className={`w-[9%] ${headerClass}`}>{t("dashboard.conversations.columns.lasted")}</TableHead>
                <TableHead className={`w-[16%] ${headerClass}`}>{t("dashboard.conversations.columns.conversation")}</TableHead>
                <TableHead className={`w-[12%] ${headerClass}`}>{t("dashboard.conversations.columns.accounts")}</TableHead>
                <TableHead className={`w-[11%] ${headerClass}`}>{t("dashboard.conversations.columns.apiKey")}</TableHead>
                <TableHead className={`w-[12%] ${headerClass}`}>{t("dashboard.conversations.columns.models")}</TableHead>
                <TableHead className={`w-[8%] text-right ${headerClass}`}>{t("dashboard.conversations.columns.requests")}</TableHead>
                <TableHead className={`w-[13%] text-right ${headerClass}`}>{t("dashboard.conversations.columns.tokens")}</TableHead>
                <TableHead className={`w-[8%] text-right ${headerClass}`}>{t("dashboard.conversations.columns.cost")}</TableHead>
                <TableHead className={`w-[9%] pr-4 ${headerClass}`}>{t("dashboard.conversations.columns.details")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {conversations.map((conversation) => {
                const time = formatDateTimeLines(conversation.lastRequest, dateDisplayFormat);
                const accountLabel = conversation.representativeAccount
                  ? (accountLabelMap.get(conversation.representativeAccount) ?? conversation.representativeAccount)
                  : null;
                const isEmailLabel = !!(
                  conversation.representativeAccount &&
                  emailLabelIds.has(conversation.representativeAccount)
                );

                return (
                  <TableRow key={conversation.conversationId} className="align-top">
                    <TableCell className="dashboard-conversation-last-request pl-4 align-top" data-mobile-label={t("dashboard.conversations.columns.lastRequest")}>
                      <span className="dashboard-mobile-label" aria-hidden="true">{t("dashboard.conversations.columns.lastRequest")}</span>
                      <div className="leading-tight">
                        <div className="text-sm font-medium">{time.primary}</div>
                        <div className="text-xs text-muted-foreground">{time.secondary}</div>
                      </div>
                    </TableCell>
                    <TableCell className="dashboard-conversation-lasted align-top font-mono text-xs tabular-nums" data-mobile-label={t("dashboard.conversations.columns.lasted")}>
                      <span className="dashboard-mobile-label" aria-hidden="true">{t("dashboard.conversations.columns.lasted")}</span>
                      {formatConversationDuration(conversation.firstRequest, conversation.lastRequest)}
                    </TableCell>
                    <TableCell className="dashboard-conversation-id max-w-0 align-top" data-mobile-label={t("dashboard.conversations.columns.conversation")}>
                      <span className="dashboard-mobile-label" aria-hidden="true">{t("dashboard.conversations.columns.conversation")}</span>
                      <span className="block truncate font-mono text-xs" title={conversation.conversationId}>
                        <span translate="no">{conversation.conversationId || "—"}</span>
                      </span>
                    </TableCell>
                    <TableCell className="dashboard-conversation-accounts align-top" data-mobile-label={t("dashboard.conversations.columns.accounts")}>
                      <span className="dashboard-mobile-label" aria-hidden="true">{t("dashboard.conversations.columns.accounts")}</span>
                      <AggregateValue
                        value={accountLabel}
                        remaining={conversation.remainingAccountCount}
                        blurred={blurred && isEmailLabel}
                      />
                    </TableCell>
                    <TableCell className="dashboard-conversation-api-key max-w-0 truncate align-top text-xs text-muted-foreground" data-mobile-label={t("dashboard.conversations.columns.apiKey")}>
                      <span className="dashboard-mobile-label" aria-hidden="true">{t("dashboard.conversations.columns.apiKey")}</span>
                      {conversation.apiKeyName || "—"}
                    </TableCell>
                    <TableCell className="dashboard-conversation-models align-top" data-mobile-label={t("dashboard.conversations.columns.models")}>
                      <span className="dashboard-mobile-label" aria-hidden="true">{t("dashboard.conversations.columns.models")}</span>
                      <AggregateValue
                        value={conversation.representativeModel}
                        remaining={conversation.remainingModelCount}
                        mono
                        translateNo
                      />
                    </TableCell>
                    <TableCell className="dashboard-conversation-requests text-right align-top font-mono text-xs tabular-nums" data-mobile-label={t("dashboard.conversations.columns.requests")}>
                      <span className="dashboard-mobile-label" aria-hidden="true">{t("dashboard.conversations.columns.requests")}</span>
                      {formatNumber(conversation.requestCount)}
                    </TableCell>
                    <TableCell className="dashboard-conversation-tokens text-right align-top font-mono text-xs tabular-nums" data-mobile-label={t("dashboard.conversations.columns.tokens")}>
                      <span className="dashboard-mobile-label" aria-hidden="true">{t("dashboard.conversations.columns.tokens")}</span>
                      <div>{formatCompactNumber(conversation.totalTokens)}</div>
                      <div className="dashboard-token-breakdown mt-1 text-[11px] font-sans text-muted-foreground">
                        {t("common.units.input")}: {formatCompactNumber(conversation.inputTokens)} · {t("common.units.output")}: {formatCompactNumber(conversation.outputTokens)}
                      </div>
                      <div className="dashboard-token-cache mt-1 text-[11px] font-sans text-muted-foreground">
                        {t("dashboard.conversations.cached", {
                          count: formatCachedTokenCount(conversation.cachedInputTokens),
                        })}
                      </div>
                    </TableCell>
                    <TableCell className="dashboard-conversation-cost text-right align-top font-mono text-xs tabular-nums" data-mobile-label={t("dashboard.conversations.columns.cost")}>
                      <span className="dashboard-mobile-label" aria-hidden="true">{t("dashboard.conversations.columns.cost")}</span>
                      {formatCurrency(conversation.totalCostUsd)}
                    </TableCell>
                    <TableCell className="dashboard-conversation-details pr-4 align-top" data-mobile-label={t("dashboard.conversations.columns.details")}>
                      <span className="dashboard-mobile-label" aria-hidden="true">{t("dashboard.conversations.columns.details")}</span>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-7 px-2 text-[11px]"
                        onClick={() => onSelect(conversation.conversationId)}
                        aria-label={t("dashboard.conversations.viewDetailsAria", {
                          id: conversation.conversationId,
                        })}
                      >
                        {t("dashboard.conversations.viewDetails")}
                      </Button>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      </div>
      {paginationControls}
    </div>
  );
}

function AggregateValue({
  value,
  remaining,
  mono = false,
  translateNo = false,
  blurred = false,
}: {
  value: string | null | undefined;
  remaining: number;
  mono?: boolean;
  translateNo?: boolean;
  blurred?: boolean;
}) {
  const { t } = useTranslation();

  return (
    <div className="min-w-0 leading-tight">
      <div className={`truncate text-sm ${mono ? "font-mono text-xs" : ""}`} title={blurred ? undefined : value ?? undefined}>
        {blurred ? (
          <span className="privacy-blur" translate={translateNo ? "no" : undefined}>{value || "—"}</span>
        ) : (
          <span translate={translateNo ? "no" : undefined}>{value || "—"}</span>
        )}
      </div>
      {remaining > 0 ? (
        <div className="mt-1 text-[11px] text-muted-foreground">
          {t("dashboard.conversations.more", { count: remaining })}
        </div>
      ) : null}
    </div>
  );
}

function formatCachedTokenCount(value: number | null | undefined): string {
  return value == null ? "—" : formatCompactNumber(value);
}
