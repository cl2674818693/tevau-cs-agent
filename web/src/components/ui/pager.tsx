import { cn } from "../../lib/utils";

/** 生成页码窗口：首页、末页、当前页±1，缺口用 "…" 占位。 */
function pageItems(page: number, totalPages: number): (number | "…")[] {
  const pages = new Set<number>([1, totalPages, page, page - 1, page + 1]);
  const sorted = [...pages].filter((p) => p >= 1 && p <= totalPages).sort((a, b) => a - b);
  const out: (number | "…")[] = [];
  let prev = 0;
  for (const p of sorted) {
    if (prev && p - prev > 1) out.push("…");
    out.push(p);
    prev = p;
  }
  return out;
}

/** 页码式分页器：上一页 / 页码 / 下一页 + 总条数。total<=pageSize 时只显示总条数。 */
export function Pager({
  page,
  total,
  pageSize,
  onChange,
  className,
}: {
  page: number;
  total: number;
  pageSize: number;
  onChange: (page: number) => void;
  className?: string;
}) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const go = (p: number) => {
    if (p >= 1 && p <= totalPages && p !== page) onChange(p);
  };
  const btn =
    "min-w-8 rounded border border-line px-2 py-1 text-body3 disabled:opacity-40 " +
    "disabled:pointer-events-none hover:bg-surface-container";
  return (
    <div className={cn("flex flex-wrap items-center gap-1.5", className)}>
      <button type="button" className={btn} onClick={() => go(page - 1)} disabled={page <= 1}>
        上一页
      </button>
      {totalPages > 1 &&
        pageItems(page, totalPages).map((it, i) =>
          it === "…" ? (
            <span key={`gap-${i}`} className="px-1 text-body3 text-ink-secondary">
              …
            </span>
          ) : (
            <button
              key={it}
              type="button"
              onClick={() => go(it)}
              aria-current={it === page ? "page" : undefined}
              className={cn(
                btn,
                it === page && "border-brand bg-brand text-ink-onbrand hover:bg-brand",
              )}
            >
              {it}
            </button>
          ),
        )}
      <button
        type="button"
        className={btn}
        onClick={() => go(page + 1)}
        disabled={page >= totalPages}
      >
        下一页
      </button>
      <span className="ml-2 text-footnote text-ink-secondary">共 {total} 条</span>
    </div>
  );
}
