import type { ColumnDef } from "@tanstack/react-table";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import {
  listToolPolicies,
  POLICY_ROLES,
  type ToolPolicy,
  TOOL_NAMES,
  upsertToolPolicies,
} from "../../api/adminToolPolicies";
import { DataTable } from "../../components/admin/data-table/DataTable";
import { DataTableColumnHeader } from "../../components/admin/data-table/DataTableColumnHeader";
import { DataTableToolbar } from "../../components/admin/data-table/DataTableToolbar";
import { Alert } from "../../components/ui/alert";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { Skeleton } from "../../components/ui/skeleton";
import { Switch } from "../../components/ui/switch";
import { useStaffSession } from "../../hooks/useStaffSession";

// ── Types ─────────────────────────────────────────────────────────────────────

type FlatRow = {
  tool_name: string;
  role: string;
  allowed: number;
  unmask_allowed: number;
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function emptyRows(): FlatRow[] {
  const out: FlatRow[] = [];
  for (const t of TOOL_NAMES)
    for (const r of POLICY_ROLES)
      out.push({ tool_name: t, role: r, allowed: 0, unmask_allowed: 0 });
  return out;
}

function applyApiRows(rows: ToolPolicy[]): FlatRow[] {
  const base = emptyRows();
  for (const row of rows) {
    const found = base.find(
      (r) => r.tool_name === row.tool_name && r.role === row.role,
    );
    if (found) {
      found.allowed = Number(row.allowed);
      found.unmask_allowed = Number(row.unmask_allowed);
    }
  }
  return base;
}

// ── Columns ───────────────────────────────────────────────────────────────────

function buildColumns(
  setRows: React.Dispatch<React.SetStateAction<FlatRow[]>>,
  readonly: boolean,
): ColumnDef<FlatRow>[] {
  function toggle(row: FlatRow, field: "allowed" | "unmask_allowed") {
    setRows((prev) =>
      prev.map((r) =>
        r.tool_name === row.tool_name && r.role === row.role
          ? { ...r, [field]: r[field] === 1 ? 0 : 1 }
          : r,
      ),
    );
  }

  return [
    {
      accessorKey: "tool_name",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="工具" />
      ),
      cell: ({ row }) => (
        <span className="font-mono text-xs">{row.original.tool_name}</span>
      ),
      enableSorting: true,
    },
    {
      accessorKey: "role",
      header: "角色",
      cell: ({ row }) => (
        <Badge variant="neutral">{row.original.role}</Badge>
      ),
      enableSorting: false,
    },
    {
      accessorKey: "allowed",
      header: "允许调用",
      cell: ({ row }) => (
        <Switch
          checked={row.original.allowed === 1}
          onCheckedChange={() => toggle(row.original, "allowed")}
          disabled={readonly}
          aria-label={`${row.original.tool_name}/${row.original.role}/allowed`}
        />
      ),
      enableSorting: false,
    },
    {
      accessorKey: "unmask_allowed",
      header: "允许解锁",
      cell: ({ row }) => (
        <Switch
          checked={row.original.unmask_allowed === 1}
          onCheckedChange={() => toggle(row.original, "unmask_allowed")}
          disabled={readonly}
          aria-label={`${row.original.tool_name}/${row.original.role}/unmask`}
        />
      ),
      enableSorting: false,
    },
  ];
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

export function ToolPoliciesRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "engineer" || role === "admin";

  const [rows, setRows] = useState<FlatRow[]>(emptyRows);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [saving, setSaving] = useState(false);

  function reload() {
    if (!token) return;
    setLoading(true);
    listToolPolicies(token)
      .then((data) => setRows(applyApiRows(data)))
      .catch((e: unknown) =>
        setLoadError(e instanceof Error ? e.message : "加载失败"),
      )
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token || !allowed) {
      setLoadError("需要工程或管理员权限");
      setLoading(false);
      return;
    }
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role]);

  async function save() {
    if (!token) return;
    setSaving(true);
    try {
      await upsertToolPolicies(token, rows);
      toast.success("已保存（缓存已刷新）");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  const columns = useMemo(
    () => buildColumns(setRows, !allowed),
    [allowed],
  );

  return (
    <PageContainer width="wide">
      <PageHeader
        title="工具策略"
        actions={
          allowed && (
            <Button size="sm" onClick={save} disabled={saving || loading}>
              {saving ? "保存中…" : "保存"}
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
              searchColumn="tool_name"
              placeholder="搜索工具名…"
            />
          )}
        />
      )}

      <p className="mt-2 text-xs text-muted-foreground">
        admin 角色默认全部允许，不在矩阵中显示。空表回退到 M1 默认白名单。
      </p>
    </PageContainer>
  );
}
