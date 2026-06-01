import { Check, ChevronRight, Loader2, Wrench, X } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { cn } from "../lib/utils";
import type { ToolCallShown } from "../types";

function statusIcon(ok: boolean | undefined) {
  return ok === undefined ? Loader2 : ok ? Check : X;
}

/** C 端：仅显示语言化进度，不暴露工具名/JSON（spec §6.2）。 */
function CToolChip({ tc }: { tc: ToolCallShown }) {
  const { t } = useTranslation();
  const Icon = statusIcon(tc.ok);
  return (
    <div className="inline-flex items-center gap-1.5 px-2 py-1 rounded-sm bg-soft-brand border border-brand/20 text-brand text-body3">
      <Icon className={cn("h-3 w-3", tc.ok === undefined && "animate-spin")} />
      <span>{t(`chat.toolChip.${tc.name}`, { defaultValue: t("chat.toolChip.default") })}</span>
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
    <div className="rounded-sm bg-surface-subtle">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-1.5 px-2 py-1.5 text-body3 text-ink-secondary hover:bg-surface-hover rounded-sm transition-colors"
      >
        <Wrench className="h-3.5 w-3.5" />
        <span className="flex-1 text-left font-mono">{tc.name}</span>
        <Icon className={cn("h-3.5 w-3.5", color, tc.ok === undefined && "animate-spin")} />
        <ChevronRight
          className={cn("h-3.5 w-3.5 transition-transform duration-300", open && "rotate-90")}
        />
      </button>
      {open && (
        <pre className="px-2 pb-2 text-body4 text-ink-secondary font-mono overflow-x-auto whitespace-pre-wrap break-all">
          {JSON.stringify(tc.input, null, 2)}
        </pre>
      )}
    </div>
  );
}
