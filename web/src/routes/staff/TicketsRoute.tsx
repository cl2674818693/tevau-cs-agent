import type { ColumnDef } from "@tanstack/react-table";
import { format } from "date-fns";
import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { listTickets, type Ticket, type TicketStatus } from "../../api/staff";
import { DataTable } from "../../components/admin/data-table/DataTable";
import { DataTableColumnHeader } from "../../components/admin/data-table/DataTableColumnHeader";
import { DataTableToolbar } from "../../components/admin/data-table/DataTableToolbar";
import { Alert } from "../../components/ui/alert";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { Skeleton } from "../../components/ui/skeleton";
import { useStaffSession } from "../../hooks/useStaffSession";

const PAGE_SIZE = 50;

// ── Status meta ───────────────────────────────────────────────────────────────

const STATUS_META: Record<
  TicketStatus,
  { label: string; variant: "pending" | "info" | "success" | "neutral" }
> = {
  pending: { label: "待处理", variant: "pending" },
  in_progress: { label: "进行中", variant: "info" },
  resolved: { label: "已解决", variant: "success" },
  closed: { label: "已关闭", variant: "neutral" },
};

// ── Severity badge ─────────────────────────────────────────────────────────────

const SEVERITY_VARIANT: Record<
  string,
  "destructive" | "error" | "pending" | "secondary"
> = {
  p0: "destructive",
  p1: "error",
  p2: "pending",
  p3: "secondary",
};

function SeverityBadge({ value }: { value: string | null }) {
  if (!value) return <span className="text-muted-foreground">—</span>;
  const v = value.toLowerCase();
  return (
    <Badge variant={SEVERITY_VARIANT[v] ?? "outline"} className="font-mono">
      {value.toUpperCase()}
    </Badge>
  );
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatDateTime(val: string) {
  try {
    return format(new Date(val), "yyyy-MM-dd HH:mm");
  } catch {
    return val;
  }
}

// ── Columns ───────────────────────────────────────────────────────────────────

const columns: ColumnDef<Ticket>[] = [
  {
    accessorKey: "external_id",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="工单号" />
    ),
    cell: ({ row }) => (
      <Link
        to={`/staff/tickets/${row.original.external_id}`}
        className="font-mono text-xs text-primary hover:underline"
      >
        {row.original.external_id}
      </Link>
    ),
    enableSorting: true,
  },
  {
    accessorKey: "category",
    header: "分类",
    cell: ({ row }) =>
      row.original.category ?? (
        <span className="text-muted-foreground">—</span>
      ),
    enableSorting: false,
  },
  {
    accessorKey: "severity",
    header: "严重度",
    cell: ({ row }) => <SeverityBadge value={row.original.severity} />,
    enableSorting: false,
  },
  {
    accessorKey: "status",
    header: "状态",
    cell: ({ row }) => {
      const meta =
        STATUS_META[row.original.status] ?? STATUS_META.in_progress;
      return <Badge variant={meta.variant}>{meta.label}</Badge>;
    },
    enableSorting: false,
  },
  {
    accessorKey: "created_at",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="创建时间" />
    ),
    cell: ({ row }) => (
      <span className="whitespace-nowrap font-mono text-xs text-muted-foreground">
        {formatDateTime(row.original.created_at)}
      </span>
    ),
    enableSorting: true,
    sortDescFirst: true,
  },
  {
    accessorKey: "conversation_id",
    header: "关联会话",
    cell: ({ row }) => (
      <Link
        to={`/staff/conversations/${row.original.conversation_id}/logs`}
        className="font-mono text-xs text-primary hover:underline"
      >
        #{row.original.conversation_id}
      </Link>
    ),
    enableSorting: false,
  },
];

// ── Filter chips ──────────────────────────────────────────────────────────────

const STATUS_OPTIONS: { value: TicketStatus | ""; label: string }[] = [
  { value: "", label: "全部状态" },
  { value: "pending", label: "待处理" },
  { value: "in_progress", label: "进行中" },
  { value: "resolved", label: "已解决" },
  { value: "closed", label: "已关闭" },
];

const SEVERITY_FILTER_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "全部严重度" },
  { value: "p0", label: "P0" },
  { value: "p1", label: "P1" },
  { value: "p2", label: "P2" },
  { value: "p3", label: "P3" },
];

function FilterChips({
  status,
  onStatus,
  severity,
  onSeverity,
}: {
  status: TicketStatus | "";
  onStatus: (v: TicketStatus | "") => void;
  severity: string;
  onSeverity: (v: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      <div className="flex flex-wrap gap-1">
        {STATUS_OPTIONS.map((o) => (
          <Button
            key={o.value}
            size="sm"
            variant={status === o.value ? "default" : "outline"}
            onClick={() => onStatus(o.value as TicketStatus | "")}
            className="h-7 px-2.5 text-xs"
          >
            {o.label}
          </Button>
        ))}
      </div>
      <div className="flex flex-wrap gap-1">
        {SEVERITY_FILTER_OPTIONS.map((o) => (
          <Button
            key={o.value}
            size="sm"
            variant={severity === o.value ? "default" : "outline"}
            onClick={() => onSeverity(o.value)}
            className="h-7 px-2.5 text-xs"
          >
            {o.label}
          </Button>
        ))}
      </div>
    </div>
  );
}

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

// eslint-disable-next-line max-lines-per-function -- 工单列表页：筛选区 + 表格 + 加载更多
export function TicketsRoute() {
  const { token } = useStaffSession();
  const nav = useNavigate();

  const [status, setStatus] = useState<TicketStatus | "">("");
  const [severity, setSeverity] = useState("");
  const [rows, setRows] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [hasMore, setHasMore] = useState(false);

  const buildFilter = useCallback(
    (beforeId?: string) => ({
      open: status === "" ? undefined : status !== "closed" && status !== "resolved",
      severity: severity || undefined,
      beforeId,
      limit: PAGE_SIZE,
    }),
    [status, severity],
  );

  useEffect(() => {
    if (!token) {
      nav("/staff/login");
      return;
    }
    setLoading(true);
    setLoadError("");
    listTickets(token, buildFilter())
      .then((data) => {
        setRows(data);
        setHasMore(data.length >= PAGE_SIZE);
      })
      .catch(() => setLoadError("加载失败"))
      .finally(() => setLoading(false));
  }, [token, buildFilter, nav]);

  function loadMore() {
    if (!token || rows.length === 0) return;
    const lastId = rows[rows.length - 1].external_id;
    listTickets(token, buildFilter(lastId))
      .then((data) => {
        setRows((prev) => [...prev, ...data]);
        setHasMore(data.length >= PAGE_SIZE);
      })
      .catch(() => setLoadError("加载更多失败"));
  }

  return (
    <PageContainer width="wide">
      <PageHeader title="工单" />

      <FilterChips
        status={status}
        onStatus={setStatus}
        severity={severity}
        onSeverity={setSeverity}
      />

      {loadError && (
        <Alert variant="destructive" className="mt-3">
          {loadError}
        </Alert>
      )}

      <div className="mt-3">
        {loading ? (
          <SkeletonRows />
        ) : (
          <DataTable
            columns={columns}
            data={rows}
            toolbar={(t) => (
              <DataTableToolbar
                table={t}
                searchColumn="external_id"
                placeholder="搜索工单号…"
              />
            )}
          />
        )}
      </div>

      {hasMore && !loading && rows.length > 0 && (
        <div className="mt-3">
          <Button variant="outline" size="sm" onClick={loadMore}>
            加载更多
          </Button>
        </div>
      )}
    </PageContainer>
  );
}
