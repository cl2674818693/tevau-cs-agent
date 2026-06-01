import type { ColumnDef } from "@tanstack/react-table";
import { useState } from "react";
import { Link } from "react-router-dom";

import { listStaffConversations } from "../../api/staff";
import type { StaffConversation } from "../../api/staff";
import { DataTable } from "../../components/admin/data-table/DataTable";
import { DataTableToolbar } from "../../components/admin/data-table/DataTableToolbar";
import { Alert } from "../../components/ui/alert";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { FilterTabs } from "../../components/ui/filter-tabs";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { Skeleton } from "../../components/ui/skeleton";
import { Switch } from "../../components/ui/switch";
import { useAsyncData } from "../../hooks/useAsyncData";
import { useStaffSession } from "../../hooks/useStaffSession";

const FILTER_OPTIONS: { value: string; label: string }[] = [
  { value: "human_pending", label: "待人工" },
  { value: "human_takeover", label: "人工接管" },
  { value: "all", label: "全部" },
  { value: "risk", label: "有风险信号" },
];

// 风险角标：变量驱动，按真值显示（兼容 boolean / 0|1）
// 统一用 outline + 语义色：列表里风险只是提示，不是 alert，不实色填充避免喧宾夺主
const RISK_BADGES: {
  key: keyof StaffConversation;
  label: string;
  className: string;
}[] = [
  { key: "has_failed", label: "失败", className: "border-destructive/40 text-destructive" },
  { key: "has_downvote", label: "差评", className: "border-destructive/40 text-destructive" },
  { key: "has_out_of_scope", label: "范围外", className: "border-amber-500/40 text-amber-600 dark:text-amber-500" },
  { key: "has_empty_tool", label: "空结果", className: "border-muted-foreground/40 text-muted-foreground" },
  { key: "needs_review", label: "待复核", className: "border-sky-500/40 text-sky-600 dark:text-sky-500" },
];

function buildColumns(
  canSpectate: boolean,
): ColumnDef<StaffConversation>[] {
  return [
    {
      accessorKey: "id",
      header: "会话 ID",
      cell: ({ row }) => (
        <Link
          to={`/staff/conversations/${row.original.id}`}
          className="font-mono text-xs text-primary hover:underline"
        >
          #{row.original.id}
        </Link>
      ),
    },
    {
      accessorKey: "user_type",
      header: "用户类型",
      cell: ({ row }) => (
        <span className="text-xs">
          {row.original.user_type === "c" ? "C 端用户" : "BU"}
        </span>
      ),
    },
    {
      accessorKey: "subject_id",
      header: "Subject",
      cell: ({ row }) => (
        <span className="font-mono text-xs text-muted-foreground">
          {row.original.subject_id}
        </span>
      ),
    },
    {
      accessorKey: "mode",
      header: "模式",
      cell: ({ row }) => (
        <Badge variant="secondary">{row.original.mode}</Badge>
      ),
    },
    {
      accessorKey: "assigned_staff_id",
      header: "负责人",
      cell: ({ row }) => (
        <span className="font-mono text-xs text-muted-foreground">
          {row.original.assigned_staff_id ?? "—"}
        </span>
      ),
    },
    {
      id: "risk_flags",
      header: "风险",
      cell: ({ row }) => {
        const badges = RISK_BADGES.filter((b) => !!row.original[b.key]);
        if (badges.length === 0) return <span className="text-muted-foreground">—</span>;
        return (
          <div className="flex flex-wrap gap-1">
            {badges.map((b) => (
              <Badge key={b.key} variant="outline" className={b.className}>
                {b.label}
              </Badge>
            ))}
          </div>
        );
      },
    },
    {
      id: "actions",
      header: "",
      cell: ({ row }) => (
        <div className="flex items-center gap-1">
          <Button asChild variant="ghost" size="sm">
            <Link to={`/staff/conversations/${row.original.id}/logs`}>留痕</Link>
          </Button>
          {canSpectate && (
            <Button asChild variant="ghost" size="sm">
              <Link to={`/staff/conversations/${row.original.id}/spectate`}>旁观</Link>
            </Button>
          )}
        </div>
      ),
    },
  ];
}

export function ConversationsListRoute() {
  const { token, role, staffId } = useStaffSession();
  const canSpectate = role === "senior" || role === "engineer";
  const [status, setStatus] = useState<string>("human_pending");
  const [myOnly, setMyOnly] = useState(false);

  // "有风险信号"：服务端不另设 status，按全部范围 + risk_only 过滤
  const riskOnly = status === "risk";
  const apiStatus = riskOnly ? "all" : status;
  const { data, loading, error } = useAsyncData(
    () => (token ? listStaffConversations(token, apiStatus, riskOnly) : null),
    [token, apiStatus, riskOnly],
    "加载失败，请重新登录",
  );

  const rawItems = data ?? [];
  const items = myOnly
    ? rawItems.filter((c) => c.assigned_staff_id === staffId)
    : rawItems;

  const columns = buildColumns(canSpectate);

  return (
    <PageContainer>
      <PageHeader title="会话" />

      {/* Filter bar */}
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <FilterTabs value={status} onChange={setStatus} options={FILTER_OPTIONS} />
        <label className="flex cursor-pointer items-center gap-1.5 text-sm">
          <Switch
            checked={myOnly}
            onCheckedChange={setMyOnly}
          />
          我负责的
        </label>
      </div>

      {error && (
        <Alert variant="destructive" className="mb-3">
          {error}
        </Alert>
      )}

      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full rounded-md" />
          ))}
        </div>
      ) : (
        <DataTable
          columns={columns}
          data={items}
          toolbar={(table) => (
            <DataTableToolbar
              table={table}
              searchColumn="subject_id"
              placeholder="搜索 Subject ID…"
            />
          )}
        />
      )}
    </PageContainer>
  );
}
