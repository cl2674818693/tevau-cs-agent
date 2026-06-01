import type { ColumnDef } from "@tanstack/react-table";
import { useCallback, useState } from "react";
import { Link } from "react-router-dom";

import {
  getGapConversations,
  getKnowledgeGaps,
  getToolHealth,
  type GapConversation,
  type GapKind,
  type InsightsRange,
  type KnowledgeGaps,
  type ToolHealth,
} from "../../api/staff";
import { DataTable } from "../../components/admin/data-table/DataTable";
import { DataTableToolbar } from "../../components/admin/data-table/DataTableToolbar";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { Skeleton } from "../../components/ui/skeleton";
import { useAsyncData } from "../../hooks/useAsyncData";
import { useStaffSession } from "../../hooks/useStaffSession";

// ── Range helpers ─────────────────────────────────────────────────────────────

type RangeKey = "7d" | "30d" | "all";

const RANGE_OPTIONS: { key: RangeKey; label: string }[] = [
  { key: "7d", label: "近 7 天" },
  { key: "30d", label: "近 30 天" },
  { key: "all", label: "全部" },
];

function rangeOf(key: RangeKey): InsightsRange {
  if (key === "all") return {};
  const days = key === "7d" ? 7 : 30;
  const from = new Date(Date.now() - days * 24 * 60 * 60 * 1000);
  // 后端按 created_at 字符串字典序比较，格式必须匹配 now_str()："YYYY-MM-DD HH:MM:SS"(UTC,无T无Z)
  return { from: from.toISOString().slice(0, 19).replace("T", " ") };
}

// ── Gap cards ─────────────────────────────────────────────────────────────────

const CARDS: { key: keyof KnowledgeGaps; kind: GapKind; label: string; hint: string }[] = [
  {
    key: "out_of_scope",
    kind: "out_of_scope",
    label: "范围外",
    hint: "话题分类判为 no（AI 答不了/超范围）",
  },
  {
    key: "failed_turns",
    kind: "failed",
    label: "失败回合",
    hint: "LLM/工具失败或僵尸超时被标 failed",
  },
  { key: "thumbs_down", kind: "thumbs_down", label: "差评 👎", hint: "用户对 AI 回复点踩" },
  {
    key: "human_handoff",
    kind: "human_handoff",
    label: "转人工",
    hint: "会话从 AI 切换到人工接管",
  },
];

// ── Tool health columns ───────────────────────────────────────────────────────

const toolColumns: ColumnDef<ToolHealth>[] = [
  {
    accessorKey: "tool_name",
    header: "工具",
    cell: ({ row }) => (
      <span className="font-mono text-xs">{row.original.tool_name}</span>
    ),
  },
  {
    accessorKey: "calls",
    header: "调用数",
    cell: ({ row }) => row.original.calls,
  },
  {
    accessorKey: "empty",
    header: "空结果数",
    cell: ({ row }) => row.original.empty,
  },
  {
    accessorKey: "empty_rate",
    header: "空结果率",
    cell: ({ row }) => {
      const hot = row.original.empty_rate > 0.5;
      return (
        <span className={hot ? "text-destructive font-medium" : undefined}>
          {(row.original.empty_rate * 100).toFixed(0)}%
        </span>
      );
    },
  },
  {
    accessorKey: "rejected",
    header: "被拒数",
    cell: ({ row }) => (
      <span className={row.original.rejected > 0 ? "text-destructive font-medium" : undefined}>
        {row.original.rejected}
      </span>
    ),
  },
];

// ── Gap conversations columns ─────────────────────────────────────────────────

const drillColumns: ColumnDef<GapConversation>[] = [
  {
    accessorKey: "conversation_id",
    header: "会话",
    cell: ({ row }) => (
      <Link
        to={`/staff/conversations/${row.original.conversation_id}/logs`}
        className="font-mono text-xs text-primary hover:underline"
      >
        #{row.original.conversation_id}
      </Link>
    ),
  },
  {
    accessorKey: "last_at",
    header: "最近时间",
    cell: ({ row }) => (
      <span className="whitespace-nowrap font-mono text-xs text-muted-foreground">
        {row.original.last_at}
      </span>
    ),
  },
];

// ── Loading skeleton ──────────────────────────────────────────────────────────

function SkeletonRows() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 6 }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full rounded-md" />
      ))}
    </div>
  );
}

// ── Drill panel ───────────────────────────────────────────────────────────────

function DrillPanel({
  token,
  kind,
  rangeKey,
  label,
}: {
  token: string;
  kind: GapKind;
  rangeKey: RangeKey;
  label: string;
}) {
  const rangeLabel = RANGE_OPTIONS.find((o) => o.key === rangeKey)?.label ?? "";
  const { data, loading, error } = useAsyncData(
    () => getGapConversations(token, kind, { ...rangeOf(rangeKey), limit: 50 }),
    [token, kind, rangeKey],
    "下钻加载失败",
  );
  const rows = data ?? [];

  return (
    <Card className="mt-3 px-3 py-3">
      <div className="mb-2 text-sm text-muted-foreground">
        {label} · {rangeLabel} · 最近 50 个会话
      </div>
      {error && (
        <Alert variant="destructive" className="mb-2">
          {error}
        </Alert>
      )}
      {loading ? (
        <SkeletonRows />
      ) : (
        <DataTable
          columns={drillColumns}
          data={rows}
          toolbar={(t) => (
            <DataTableToolbar table={t} searchColumn="conversation_id" placeholder="搜索会话号…" />
          )}
          empty="暂无记录"
        />
      )}
    </Card>
  );
}

// ── Route ─────────────────────────────────────────────────────────────────────

export function InsightsRoute() {
  const { token } = useStaffSession();
  const [rangeKey, setRangeKey] = useState<RangeKey>("7d");
  const [openKind, setOpenKind] = useState<GapKind | null>(null);

  const range = rangeOf(rangeKey);

  const {
    data: gapsAndTools,
    loading,
    error,
  } = useAsyncData(
    () =>
      token
        ? Promise.all([getKnowledgeGaps(token, range), getToolHealth(token, range)])
        : null,
    [token, rangeKey],
    "加载失败",
  );

  const gaps = gapsAndTools?.[0] ?? null;
  const tools = gapsAndTools?.[1] ?? [];

  const drill = useCallback(
    (kind: GapKind) => {
      setOpenKind((prev) => (prev === kind ? null : kind));
    },
    [],
  );

  return (
    <PageContainer width="wide">
      <PageHeader title="知识缺口" />

      {/* Range selector */}
      <div className="mb-3 flex items-center gap-2">
        {RANGE_OPTIONS.map((o) => (
          <Button
            key={o.key}
            size="sm"
            variant={rangeKey === o.key ? "default" : "outline"}
            onClick={() => {
              setRangeKey(o.key);
              setOpenKind(null);
            }}
            className="h-7 px-2.5 text-xs"
          >
            {o.label}
          </Button>
        ))}
      </div>

      {error && (
        <Alert variant="destructive" className="mb-3">
          {error}
        </Alert>
      )}

      {loading ? (
        <SkeletonRows />
      ) : (
        <>
          {/* Gap summary cards */}
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {CARDS.map((c) => {
              const active = openKind === c.kind;
              return (
                <button
                  key={c.key}
                  type="button"
                  onClick={() => drill(c.kind)}
                  className={
                    "rounded-md border px-3 py-4 text-left transition-colors " +
                    (active
                      ? "border-primary bg-primary/10"
                      : "border-border bg-card hover:border-primary")
                  }
                >
                  <div className="text-2xl font-semibold text-foreground">
                    {gaps ? gaps[c.key] : "-"}
                  </div>
                  <div className="mt-1 text-sm font-medium text-foreground">{c.label}</div>
                  <div className="mt-1 text-xs text-muted-foreground">{c.hint}</div>
                </button>
              );
            })}
          </div>

          {/* Drill-down panel */}
          {openKind && token && (
            <DrillPanel
              token={token}
              kind={openKind}
              rangeKey={rangeKey}
              label={CARDS.find((c) => c.kind === openKind)?.label ?? ""}
            />
          )}

          {/* Tool health table */}
          <div className="mt-6">
            <h3 className="mb-3 text-base font-semibold text-foreground">工具健康</h3>
            <DataTable
              columns={toolColumns}
              data={tools}
              toolbar={(t) => (
                <DataTableToolbar table={t} searchColumn="tool_name" placeholder="搜索工具名…" />
              )}
              empty="暂无记录"
            />
          </div>
        </>
      )}

      <p className="mt-4 text-xs text-muted-foreground">
        明细可在「全局工具审计」或具体会话的留痕页查看。
      </p>
    </PageContainer>
  );
}
