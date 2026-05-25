import { Wifi } from "lucide-react";

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
    <header className="safe-top sticky top-0 z-10 flex items-center justify-between px-page py-3 bg-surface-card border-b border-line">
      <div className="flex items-center gap-3">
        <div className="h-9 w-9 rounded-md grid place-items-center bg-brand">
          <span className="text-ink-onbrand font-bold text-body0">T</span>
        </div>
        <div className="flex flex-col">
          <div className="text-sh3 font-bold text-ink-primary leading-none">Tevau 客服</div>
          <div className="flex items-center gap-1.5 mt-1">
            {mode !== "human_takeover" && (
              <span className="w-1.5 h-1.5 rounded-full bg-status-success" />
            )}
            <span className="text-footnote text-ink-secondary">
              {mode === "human_takeover" ? `客服 ${staffName ?? ""} · 已认证` : "在线 · 智能助手"}
            </span>
          </div>
        </div>
      </div>
      {sending && (
        <button
          onClick={onStop}
          className="px-3 py-1.5 rounded text-body3 text-ink-secondary border border-line hover:bg-surface-hover transition-colors"
        >
          停止生成
        </button>
      )}
    </header>
  );
}

export function EmptyState({ greeting }: { greeting: string }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center text-center px-8 gap-3">
      <div className="h-14 w-14 rounded-xl grid place-items-center bg-soft-brand">
        <span className="text-brand font-bold text-h2">T</span>
      </div>
      <div className="text-sh1 font-bold text-ink-primary">你好，我是 Tevau 助手</div>
      <p className="text-body2 text-ink-secondary leading-relaxed max-w-[320px]">{greeting}</p>
    </div>
  );
}

export function LoadingView() {
  return (
    <div className="mx-auto flex h-full max-w-[720px] items-center justify-center bg-surface-page text-ink-secondary">
      <div className="animate-pulse text-body2">正在连接 Tevau 客服…</div>
    </div>
  );
}

export function ErrorView({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="mx-auto flex h-full max-w-[720px] flex-col items-center justify-center gap-3 bg-surface-page">
      <div className="text-body2 text-status-error">连接失败，请检查网络后重试。</div>
      <button
        onClick={onRetry}
        className="rounded border border-line px-4 py-2 text-body2 text-brand hover:bg-soft-brand transition-colors"
      >
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
        <div className="flex items-center justify-center gap-1.5 px-page py-1.5 bg-soft-warning border-b border-status-warning/30 text-body3 text-status-warning text-center">
          <Wifi className="h-3.5 w-3.5" />
          {connection === "offline" ? "网络已断开，正在等待重新连接…" : "正在重新连接…"}
        </div>
      )}
      {limitPct >= 80 && limitPct < 100 && (
        <div className="px-page py-1.5 bg-soft-warning text-body3 text-status-warning text-center">
          您今日用量已达 {limitPct}%，建议核心问题尽快咨询。
        </div>
      )}
    </>
  );
}
