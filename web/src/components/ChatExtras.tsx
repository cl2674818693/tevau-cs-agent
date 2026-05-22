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
    <header className="safe-top sticky top-0 z-10 flex items-center justify-between px-page py-3 glass border-b border-chat-primary/20">
      <div className="flex items-center gap-3">
        <div className="h-9 w-9 rounded-lg grid place-items-center bg-chat-primary/10 border border-chat-primary/30">
          <span className="text-chat-primary font-chat-headline text-body0 font-bold">T</span>
        </div>
        <div className="flex flex-col">
          <div className="font-chat-headline text-sh3 font-bold text-chat-primary leading-none">
            Tevau AI 客服
          </div>
          <div className="flex items-center gap-1.5 mt-1">
            {mode !== "human_takeover" && (
              <span
                className="w-2 h-2 rounded-full bg-chat-primary animate-breathe"
                style={{ boxShadow: "0 0 8px rgba(34,211,238,0.8)" }}
              />
            )}
            <span className="text-footnote text-chat-on-surface-variant">
              {mode === "human_takeover"
                ? `客服 ${staffName ?? ""} · 已认证`
                : "由 AI 驱动 · 复杂问题转人工"}
            </span>
          </div>
        </div>
      </div>
      {sending && (
        <button
          onClick={onStop}
          className="px-3 py-1.5 rounded-lg border border-chat-primary/20 bg-chat-primary/5 text-body3 text-chat-primary hover:bg-chat-primary/10 transition-colors"
        >
          停止生成
        </button>
      )}
    </header>
  );
}

export function LoadingView() {
  return (
    <div className="mx-auto flex h-full max-w-[720px] items-center justify-center bg-chat-surface grid-bg text-chat-on-surface-variant">
      <div className="animate-pulse text-body2 font-chat-body">正在连接 Tevau AI 客服…</div>
    </div>
  );
}

export function ErrorView({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="mx-auto flex h-full max-w-[720px] flex-col items-center justify-center gap-3 bg-chat-surface grid-bg font-chat-body">
      <div className="text-body2 text-status-error">连接失败，请检查网络后重试。</div>
      <button
        onClick={onRetry}
        className="rounded-lg border border-chat-primary/30 px-4 py-2 text-body2 text-chat-primary hover:bg-chat-primary/10 transition-colors"
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
        <div className="flex items-center justify-center gap-1.5 px-page py-1.5 bg-chat-accent/10 border-b border-chat-accent/30 text-body3 text-chat-accent text-center">
          <Wifi className="h-3.5 w-3.5" />
          {connection === "offline" ? "网络已断开，正在等待重新连接…" : "正在重新连接…"}
        </div>
      )}
      {limitPct >= 80 && limitPct < 100 && (
        <div className="px-page py-1.5 bg-chat-accent/10 text-body3 text-chat-accent text-center">
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
          className="rounded-full glass border border-chat-primary/20 px-4 py-1.5 text-body3 text-chat-primary hover:bg-chat-primary/10 transition-colors"
        >
          {s}
        </button>
      ))}
    </div>
  );
}
