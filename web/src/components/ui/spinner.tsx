import { Loader2 } from "lucide-react";

import { cn } from "../../lib/utils";

/** 行内小转圈：按钮/局部加载用。 */
export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("h-4 w-4 animate-spin", className)} aria-hidden />;
}

/** 整块加载占位：数据页首屏 loading 用，垂直居中。 */
export function LoadingState({ children = "加载中…" }: { children?: React.ReactNode }) {
  return (
    <div
      className="flex items-center justify-center gap-2 py-12 text-body3 text-ink-secondary"
      role="status"
      aria-live="polite"
    >
      <Spinner />
      <span>{children}</span>
    </div>
  );
}
