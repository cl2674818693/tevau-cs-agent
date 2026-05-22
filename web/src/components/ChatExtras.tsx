/** ChatWindow 的辅助呈现块（拆出以控制单组件复杂度）。 */

export function ChatHeader({
  mode,
  staffName,
  sending,
  onStop,
}: {
  mode: string;
  staffName?: string;
  sending: boolean;
  onStop: () => void;
}) {
  return (
    <header className="safe-top sticky top-0 z-10 flex items-center px-page py-3 bg-surface-card border-b border-line">
      <div className="h-7 w-7 rounded bg-brand grid place-items-center mr-2">
        <span className="text-ink-primary text-body0 font-bold">T</span>
      </div>
      <div className="flex-1">
        <div className="text-sh3 text-ink-primary">Tevau AI 客服</div>
        <div className="text-footnote text-ink-secondary">
          {mode === "human_takeover"
            ? `客服 ${staffName ?? ""} · 已认证`
            : "由 AI 驱动 · 复杂问题转人工"}
        </div>
      </div>
      {sending && (
        <button onClick={onStop} className="text-body2 text-ink-secondary px-2">
          停止生成
        </button>
      )}
    </header>
  );
}

export function LoadingView() {
  return (
    <div className="mx-auto flex h-full max-w-[720px] items-center justify-center text-ink-secondary">
      <div className="animate-pulse text-body2">正在连接 Tevau AI 客服…</div>
    </div>
  );
}

export function ErrorView({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="mx-auto flex h-full max-w-[720px] flex-col items-center justify-center gap-3">
      <div className="text-body2 text-status-error">连接失败，请检查网络后重试。</div>
      <button onClick={onRetry} className="rounded border border-line px-4 py-2 text-body2">
        重试
      </button>
    </div>
  );
}

export function StatusBanners({
  connection,
  limitPct,
}: {
  connection: "online" | "offline" | "reconnecting";
  limitPct: number;
}) {
  return (
    <>
      {connection !== "online" && (
        <div className="px-page py-1.5 bg-status-warning/10 text-body3 text-status-warning text-center">
          {connection === "offline" ? "网络已断开，正在等待重新连接…" : "正在重新连接…"}
        </div>
      )}
      {limitPct >= 80 && limitPct < 100 && (
        <div className="px-page py-1.5 bg-yellow-100 text-body3 text-yellow-800 text-center">
          您今日用量已达 {limitPct}%，建议核心问题尽快咨询。
        </div>
      )}
    </>
  );
}

const SUGGESTIONS = ["我的卡为什么被锁了？", "如何对接 Open API？", "查一下我最近的订单"];

export function Suggestions({ onPick }: { onPick: (q: string) => void }) {
  return (
    <div className="px-page pb-2 flex flex-wrap gap-2">
      {SUGGESTIONS.map((s) => (
        <button
          key={s}
          onClick={() => onPick(s)}
          className="rounded-full border border-line px-3 py-1.5 text-body3 text-ink-secondary hover:bg-surface-hover"
        >
          {s}
        </button>
      ))}
    </div>
  );
}
