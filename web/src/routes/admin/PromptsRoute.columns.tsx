import type { ColumnDef } from "@tanstack/react-table";
import { Pencil } from "lucide-react";

import type { PromptAbStat } from "../../api/admin";
import { DataTableColumnHeader } from "../../components/admin/data-table/DataTableColumnHeader";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";

export type PromptRow = {
  version: string;
  rollout: number;
  isDefault: boolean;
  stat: PromptAbStat | undefined;
};

// ── Cell helpers ──────────────────────────────────────────────────────────────

function RolloutBar({ pct }: { pct: number }) {
  return (
    <div className="flex items-center gap-2 min-w-[120px]">
      <div className="h-1.5 w-24 rounded-full bg-muted overflow-hidden">
        <div className="h-full rounded-full bg-primary" style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
      <span className="text-sm tabular-nums">{pct}%</span>
    </div>
  );
}

function AbStatsCell({ s }: { s: PromptAbStat | undefined }) {
  if (!s) return <span className="text-muted-foreground text-xs">—</span>;
  const failHigh = s.failed_rate > 0.1;
  const dvHigh = s.downvote_rate > 0.2;
  return (
    <div className="flex items-center gap-3 text-xs tabular-nums">
      <span className="text-muted-foreground">{s.assistant_turns} 轮</span>
      <span className={failHigh ? "text-destructive" : "text-muted-foreground"}>
        失败 {(s.failed_rate * 100).toFixed(1)}%
      </span>
      <span className={dvHigh ? "text-destructive" : "text-muted-foreground"}>
        差评 {(s.downvote_rate * 100).toFixed(1)}%
      </span>
    </div>
  );
}

// ── Column definitions ────────────────────────────────────────────────────────

export function buildPromptColumns(
  onEdit: (row: PromptRow) => void,
): ColumnDef<PromptRow>[] {
  return [
    {
      accessorKey: "version",
      header: ({ column }) => <DataTableColumnHeader column={column} title="版本" />,
      cell: ({ row }) => <span className="font-mono text-sm">{row.original.version}</span>,
      enableSorting: true,
    },
    {
      accessorKey: "isDefault",
      header: "角色",
      cell: ({ row }) =>
        row.original.isDefault
          ? <Badge variant="info">default</Badge>
          : <Badge variant="neutral">灰度</Badge>,
      enableSorting: false,
    },
    {
      accessorKey: "rollout",
      header: "流量",
      cell: ({ row }) => <RolloutBar pct={row.original.rollout} />,
      enableSorting: false,
    },
    {
      id: "ab_stats",
      header: "A/B 表现",
      cell: ({ row }) => <AbStatsCell s={row.original.stat} />,
      enableSorting: false,
    },
    {
      id: "actions",
      header: () => null,
      cell: ({ row }) => (
        <div className="flex justify-end">
          <Button variant="ghost" size="sm" className="h-8 gap-1.5 px-2" onClick={() => onEdit(row.original)}>
            <Pencil className="h-3.5 w-3.5" />
            调整流量
          </Button>
        </div>
      ),
      enableSorting: false,
    },
  ];
}
