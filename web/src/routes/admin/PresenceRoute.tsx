import type { ColumnDef } from "@tanstack/react-table";
import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { listPresence, type Presence } from "../../api/staffPresence";
import { DataTable } from "../../components/admin/data-table/DataTable";
import { DataTableColumnHeader } from "../../components/admin/data-table/DataTableColumnHeader";
import { DataTableToolbar } from "../../components/admin/data-table/DataTableToolbar";
import { Alert } from "../../components/ui/alert";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { PageContainer, PageHeader } from "../../components/ui/page";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../components/ui/select";
import { Skeleton } from "../../components/ui/skeleton";
import { useStaffSession } from "../../hooks/useStaffSession";

// ── Columns ──────────────────────────────────────────────────────────────────

const columns: ColumnDef<Presence>[] = [
  {
    accessorKey: "staff_id",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="Staff ID" />
    ),
    enableSorting: true,
  },
  {
    accessorKey: "status",
    header: "状态",
    cell: ({ row }) => {
      const s = row.original.status;
      return (
        <Badge variant={s === "online" ? "default" : "secondary"}>
          {s === "online" ? "在线" : s === "away" ? "离开" : s}
        </Badge>
      );
    },
    filterFn: (row, _columnId, filterValue) => {
      if (!filterValue || filterValue === "all") return true;
      return row.original.status === filterValue;
    },
    enableSorting: false,
  },
  {
    accessorKey: "last_seen_at",
    header: ({ column }) => (
      <DataTableColumnHeader column={column} title="上次活跃" />
    ),
    cell: ({ row }) => {
      const raw = row.original.last_seen_at;
      try {
        return new Date(raw).toLocaleString("zh-CN", {
          year: "numeric",
          month: "2-digit",
          day: "2-digit",
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        });
      } catch {
        return raw;
      }
    },
    enableSorting: true,
  },
];

// ── Loading skeleton ─────────────────────────────────────────────────────────

function SkeletonRows() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 5 }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full rounded-md" />
      ))}
    </div>
  );
}

// ── Route ────────────────────────────────────────────────────────────────────

export function PresenceRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "supervisor" || role === "admin";
  const [rows, setRows] = useState<Presence[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  const reload = useCallback(() => {
    if (!token) return;
    setLoading(true);
    setLoadError("");
    listPresence(token)
      .then((d) => setRows(d.all))
      .catch((e: unknown) =>
        setLoadError(e instanceof Error ? e.message : "加载失败"),
      )
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => {
    if (!token) return;
    if (!allowed) {
      setLoadError("需要主管或管理员权限");
      setLoading(false);
      return;
    }
    reload();
  }, [token, role]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <PageContainer width="wide">
      <PageHeader
        title="在线状态"
        actions={
          allowed && (
            <Button
              variant="outline"
              size="sm"
              onClick={reload}
              disabled={loading}
            >
              <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
              刷新
            </Button>
          )
        }
      />

      {loadError && (
        <Alert variant="destructive" className="mb-4">
          {loadError}
        </Alert>
      )}

      {loading ? (
        <SkeletonRows />
      ) : (
        <DataTable
          columns={columns}
          data={rows}
          toolbar={(t) => (
            <DataTableToolbar
              table={t}
              searchColumn="staff_id"
              placeholder="按 staff_id 搜索…"
            >
              <Select
                value={
                  (t.getColumn("status")?.getFilterValue() as string) ?? "all"
                }
                onValueChange={(v) =>
                  t.getColumn("status")?.setFilterValue(v === "all" ? "" : v)
                }
              >
                <SelectTrigger className="h-8 w-[120px]">
                  <SelectValue placeholder="全部状态" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部状态</SelectItem>
                  <SelectItem value="online">在线</SelectItem>
                  <SelectItem value="away">离开</SelectItem>
                </SelectContent>
              </Select>
            </DataTableToolbar>
          )}
        />
      )}
    </PageContainer>
  );
}
