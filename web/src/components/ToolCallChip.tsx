import { Check, ChevronRight, Loader2, Wrench, X } from "lucide-react";
import { useState } from "react";

import { cn } from "../lib/utils";
import type { ToolCallShown } from "../types";

export function ToolCallChip({ tc }: { tc: ToolCallShown }) {
  const [open, setOpen] = useState(false);
  const Icon = tc.ok === undefined ? Loader2 : tc.ok ? Check : X;
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
