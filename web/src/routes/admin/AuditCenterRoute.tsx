import type { ColumnDef } from "@tanstack/react-table";
import { format } from "date-fns";
import { RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";

import { listAudit, type AuditEntry } from "../../api/adminAudit";
import { DataTable } from "../../components/admin/data-table/DataTable";
import { DataTableColumnHeader } from "../../components/admin/data-table/DataTableColumnHeader";
import { DataTableToolbar } from "../../components/admin/data-table/DataTableToolbar";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { DatePicker } from "../../components/ui/date-picker";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { Skeleton } from "../../components/ui/skeleton";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "../../components/ui/tooltip";
import { useStaffSession } from "../../hooks/useStaffSession";

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatDateTime(val: string) {
  try {
    return format(new Date(val), "yyyy-MM-dd HH:mm:ss");
  } catch {
    return val;
  }
}

// ── Detail cell with tooltip for long JSON ────────────────────────────────────

function DetailCell({ value }: { value: string | null }) {
  if (!value) return <span className="text-muted-foreground">—</span>;
  const truncated = value.length > 60 ? value.slice(0, 60) + "…" : value;
  if (value.length <= 60) {
    return <span className="font-mono text-xs">{value}</span>;
  }
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="cursor-help font-mono text-xs text-muted-foreground">
            {truncated}
          </span>
        </TooltipTrigger>
        <TooltipContent className="max-w-sm break-all text-xs">
          {value}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

// ── Columns ───────────────────────────────────────────────────────────────────

const columns: ColumnDef<AuditEntry>[] = [
  {
    accessorKey: "created_at",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="时间" />
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
    accessorKey: "actor",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="操作人" />
    ),
    cell: ({ row }) => (
      <span className="font-mono text-xs">{row.original.actor}</span>
    ),
    enableSorting: true,
  },
  {
    accessorKey: "action",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="动作" />
    ),
    cell: ({ row }) => (
      <span className="font-mono text-xs text-foreground">{row.original.action}</span>
    ),
    enableSorting: true,
  },
  {
    id: "target",
    header: "对象",
    cell: ({ row }) => {
      const { target_type, target_id } = row.original;
      if (!target_type) return <span className="text-muted-foreground">—</span>;
      return (
        <span className="font-mono text-xs">
          {target_type}
          {target_id ? `:${target_id}` : ""}
        </span>
      );
    },
    enableSorting: false,
  },
  {
    accessorKey: "detail_json",
    header: "详情",
    cell: ({ row }) => <DetailCell value={row.original.detail_json} />,
    enableSorting: false,
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

// ── Filter bar state ──────────────────────────────────────────────────────────

interface FilterState {
  actor: string;
  action: string;
  dateFrom: Date | undefined;
  dateTo: Date | undefined;
}

// ── Route ─────────────────────────────────────────────────────────────────────

export function AuditCenterRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "engineer" || role === "admin";

  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [filter, setFilter] = useState<FilterState>({
    actor: "",
    action: "",
    dateFrom: undefined,
    dateTo: undefined,
  });

  function reload(f: FilterState = filter) {
    if (!token) return;
    setLoading(true);
    setErr("");
    listAudit(token, {
      actor: f.actor || undefined,
      action: f.action || undefined,
    })
      .then((rows) => {
        // Client-side date filter (API doesn't support date range params)
        const from = f.dateFrom ? f.dateFrom.getTime() : null;
        // end of the "to" day
        const to = f.dateTo
          ? new Date(f.dateTo.getFullYear(), f.dateTo.getMonth(), f.dateTo.getDate(), 23, 59, 59, 999).getTime()
          : null;
        const filtered =
          from != null || to != null
            ? rows.filter((r) => {
                const t = new Date(r.created_at).getTime();
                if (from != null && t < from) return false;
                if (to != null && t > to) return false;
                return true;
              })
            : rows;
        setEntries(filtered);
      })
      .catch(() => setErr("加载失败，请重试"))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token) return;
    if (!allowed) {
      setErr("需要工程或管理员权限");
      setLoading(false);
      return;
    }
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role]);

  // Sort entries descending by created_at on initial load
  const sortedEntries = [...entries].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  );

  return (
    <PageContainer width="wide">
      <PageHeader
        title="操作审计"
        actions={
          <Button
            variant="outline"
            size="sm"
            onClick={() => reload()}
            disabled={loading}
          >
            <RefreshCw className={`mr-1.5 h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
            刷新
          </Button>
        }
      />

      {err && (
        <Alert variant="destructive" className="mb-4">
          {err}
        </Alert>
      )}

      {allowed && (
        <>
          {/* Date range + action filter */}
          <div className="mb-3 flex flex-wrap items-end gap-2">
            <DatePicker
              date={filter.dateFrom}
              onChange={(d) => setFilter((f) => ({ ...f, dateFrom: d }))}
              placeholder="开始日期"
            />
            <DatePicker
              date={filter.dateTo}
              onChange={(d) => setFilter((f) => ({ ...f, dateTo: d }))}
              placeholder="结束日期"
            />
            <Button
              variant="default"
              size="sm"
              onClick={() => reload(filter)}
              disabled={loading}
            >
              筛选
            </Button>
            {(filter.dateFrom || filter.dateTo) && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  const next = { ...filter, dateFrom: undefined, dateTo: undefined };
                  setFilter(next);
                  reload(next);
                }}
              >
                清除日期
              </Button>
            )}
          </div>

          {loading ? (
            <SkeletonRows />
          ) : (
            <DataTable
              columns={columns}
              data={sortedEntries}
              toolbar={(t) => (
                <DataTableToolbar
                  table={t}
                  searchColumn="actor"
                  placeholder="搜索操作人…"
                >
                  {/* action column filter input */}
                  {(() => {
                    const actionCol = t.getColumn("action");
                    return actionCol ? (
                      <input
                        className="h-8 w-[180px] rounded-md border border-input bg-background px-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                        placeholder="搜索动作…"
                        value={(actionCol.getFilterValue() as string) ?? ""}
                        onChange={(e) => actionCol.setFilterValue(e.target.value)}
                      />
                    ) : null;
                  })()}
                </DataTableToolbar>
              )}
              empty="暂无审计记录"
            />
          )}
        </>
      )}
    </PageContainer>
  );
}
