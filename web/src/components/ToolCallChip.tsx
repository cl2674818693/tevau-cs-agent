import { Check, ChevronRight, Loader2, Wrench, X } from "lucide-react";
import { useState } from "react";

import { cn } from "../lib/utils";
import type { ToolCallShown } from "../types";

// C 端语言化：不暴露内部工具名/JSON（spec §6.2）。
const C_LABELS: Record<string, string> = {
  query_user: "正在查询账户信息…",
  query_card: "正在查询卡片状态…",
  query_balance: "正在查询余额…",
  query_kyc: "正在查询认证状态…",
  query_transaction: "正在查询交易记录…",
  query_bu_order: "正在查询订单…",
  query_bu_request_log: "正在查询接口调用记录…",
  search_code: "正在排查问题…",
  read_file: "正在排查问题…",
  lookup_api_doc: "正在查阅接口文档…",
  create_ticket: "正在为您创建工单…",
};

function statusIcon(ok: boolean | undefined) {
  return ok === undefined ? Loader2 : ok ? Check : X;
}

/** C 端：仅显示语言化进度，不暴露工具名/JSON（spec §6.2）。 */
function CToolChip({ tc }: { tc: ToolCallShown }) {
  const Icon = statusIcon(tc.ok);
  return (
    <div className="flex items-center gap-1.5 px-2 py-1.5 text-body3 text-ink-subtle">
      <Icon className={cn("h-3.5 w-3.5", tc.ok === undefined && "animate-spin")} />
      <span>{C_LABELS[tc.name] ?? "正在为您处理…"}</span>
    </div>
  );
}

export function ToolCallChip({ tc, userType = "b" }: { tc: ToolCallShown; userType?: "c" | "b" }) {
  const [open, setOpen] = useState(false);

  if (userType === "c") return <CToolChip tc={tc} />;

  const Icon = statusIcon(tc.ok);
  const color =
    tc.ok === undefined
      ? "text-ink-secondary"
      : tc.ok
        ? "text-status-success"
        : "text-status-error";

  return (
    <div className="rounded bg-surface-container">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-1.5 px-2 py-1.5 text-body3 text-ink-subtle hover:bg-brand-disabled rounded transition-colors"
      >
        <Wrench className="h-3.5 w-3.5" />
        <span className="flex-1 text-left font-mono">{tc.name}</span>
        <Icon className={cn("h-3.5 w-3.5", color, tc.ok === undefined && "animate-spin")} />
        <ChevronRight
          className={cn("h-3.5 w-3.5 transition-transform duration-300", open && "rotate-90")}
        />
      </button>
      {open && (
        <pre className="px-2 pb-2 text-body4 text-ink-subtle font-mono overflow-x-auto whitespace-pre-wrap break-all">
          {JSON.stringify(tc.input, null, 2)}
        </pre>
      )}
    </div>
  );
}
