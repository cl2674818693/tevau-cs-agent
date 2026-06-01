import type { ColumnDef } from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { getRecentAudits } from "../../api/staff";
import type { ToolAudit } from "../../api/staff";
import { DataTable } from "../../components/admin/data-table/DataTable";
import { DataTableToolbar } from "../../components/admin/data-table/DataTableToolbar";
import { Alert } from "../../components/ui/alert";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { Pager } from "../../components/ui/pager";
import { Skeleton } from "../../components/ui/skeleton";
import { useAsyncData } from "../../hooks/useAsyncData";
import { useStaffSession } from "../../hooks/useStaffSession";

const PAGE_SIZE = 100;

const TOOL_OPTIONS = [
  "query_user",
  "query_card",
  "query_kyc",
  "query_balance",
  "query_transaction",
  "query_bu_order",
  "query_bu_request_log",
  "create_ticket",
  "search_code",
  "lookup_api_doc",
  "read_file",
];

function isEmpty(a: ToolAudit): boolean {
  return a.is_empty === 1 || a.is_empty === true;
}

// ── Columns ───────────────────────────────────────────────────────────────────

const columns: ColumnDef<ToolAudit>[] = [
  {
    accessorKey: "created_at",
    header: "时间",
    cell: ({ row }) => (
      <span className="whitespace-nowrap font-mono text-xs text-muted-foreground">
        {row.original.created_at}
      </span>
    ),
  },
  {
    accessorKey: "conversation_id",
    header: "会话",
    cell: ({ row }) =>
      row.original.conversation_id != null ? (
        <Link
          to={`/staff/conversations/${row.original.conversation_id}/logs`}
          className="font-mono text-xs text-primary hover:underline"
        >
          #{row.original.conversation_id}
        </Link>
      ) : (
        <span className="text-muted-foreground">—</span>
      ),
  },
  {
    accessorKey: "tool_name",
    header: "工具",
    cell: ({ row }) => (
      <span className="whitespace-nowrap font-mono text-xs">{row.original.tool_name}</span>
    ),
  },
  {
    id: "identity",
    header: "身份",
    cell: ({ row }) => (
      <span className="whitespace-nowrap font-mono text-xs text-muted-foreground">
        {row.original.user_type ?? "-"}
        {row.original.subject_id ? `:${row.original.subject_id}` : ""}
      </span>
    ),
  },
  {
    accessorKey: "result_count",
    header: "返回",
    cell: ({ row }) => (
      <span className={isEmpty(row.original) ? "text-destructive" : undefined}>
        {row.original.result_count ?? 0} 条
      </span>
    ),
  },
  {
    accessorKey: "duration_ms",
    header: "耗时",
    cell: ({ row }) => (
      <span className="whitespace-nowrap font-mono text-xs">{row.original.duration_ms}ms</span>
    ),
  },
  {
    accessorKey: "rejected",
    header: "状态",
    cell: ({ row }) =>
      row.original.rejected ? (
        <Badge variant="destructive">被拒：{row.original.reject_reason ?? "-"}</Badge>
      ) : (
        <Badge variant="success">ok</Badge>
      ),
  },
];

// ── Loading skeleton ──────────────────────────────────────────────────────────

function SkeletonRows() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 8 }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full rounded-md" />
      ))}
    </div>
  );
}

// ── Route ─────────────────────────────────────────────────────────────────────

// eslint-disable-next-line max-lines-per-function -- 审计页：筛选区 + 表格 + 页码分页
export function AuditsRoute() {
  const { token } = useStaffSession();

  const [rejectedOnly, setRejectedOnly] = useState(false);
  const [emptyOnly, setEmptyOnly] = useState(false);
  const [toolName, setToolName] = useState("");
  const [conversationId, setConversationId] = useState("");
  const [page, setPage] = useState(1);

  // 改任一筛选都回到第 1 页
  function onFilter<T>(setter: (v: T) => void) {
    return (v: T) => {
      setter(v);
      setPage(1);
    };
  }

  const filter = useMemo(
    () => ({
      rejectedOnly,
      emptyOnly,
      toolName: toolName || undefined,
      conversationId: conversationId.trim() || undefined,
      page,
      limit: PAGE_SIZE,
    }),
    [rejectedOnly, emptyOnly, toolName, conversationId, page],
  );

  const { data, loading, error } = useAsyncData(
    () => (token ? getRecentAudits(token, filter) : null),
    [token, filter],
    "加载失败",
  );

  const rows = data?.audits ?? [];
  const total = data?.total ?? 0;

  return (
    <PageContainer width="wide">
      <PageHeader title="工具审计" />

      {/* Filter bar */}
      <div className="mb-3 flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
        <select
          value={toolName}
          onChange={(e) => onFilter(setToolName)(e.target.value)}
          className="rounded-md border border-input bg-background px-2 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="">全部工具</option>
          {TOOL_OPTIONS.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>

        <input
          type="text"
          inputMode="numeric"
          placeholder="会话号"
          value={conversationId}
          onChange={(e) => onFilter(setConversationId)(e.target.value)}
          className="w-24 rounded-md border border-input bg-background px-2 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        />

        <Button
          size="sm"
          variant={rejectedOnly ? "default" : "outline"}
          onClick={() => onFilter(setRejectedOnly)(!rejectedOnly)}
          className="h-7 px-2.5 text-xs"
        >
          只看被拒
        </Button>

        <Button
          size="sm"
          variant={emptyOnly ? "default" : "outline"}
          onClick={() => onFilter(setEmptyOnly)(!emptyOnly)}
          className="h-7 px-2.5 text-xs"
        >
          只看空结果
        </Button>
      </div>

      {error && (
        <Alert variant="destructive" className="mb-3">
          {error}
        </Alert>
      )}

      {loading ? (
        <SkeletonRows />
      ) : (
        <DataTable
          columns={columns}
          data={rows}
          toolbar={(t) => (
            <DataTableToolbar table={t} searchColumn="tool_name" placeholder="搜索工具名…" />
          )}
          empty="暂无记录"
        />
      )}

      {!loading && total > 0 && (
        <Pager page={page} total={total} pageSize={PAGE_SIZE} onChange={setPage} className="mt-3" />
      )}
    </PageContainer>
  );
}
