import { Headphones } from "lucide-react";

/**
 * "没解决？转人工 →" 按钮。点击调 useChat.requestHandoff →
 * POST /request-human（置 human_pending + 建人工介入工单，spec §13.7）。
 */
export function HandoffButton({ onClick, disabled }: { onClick: () => void; disabled: boolean }) {
  return (
    <div className="px-page py-2">
      <button
        onClick={onClick}
        disabled={disabled}
        className="w-full flex items-center justify-center gap-2 py-2.5 rounded-full glass border border-white/10 text-body2 text-chat-on-surface-variant transition-all hover:border-chat-primary/40 hover:text-chat-primary disabled:opacity-50"
      >
        <Headphones className="h-4 w-4" />
        没解决？转人工 →
      </button>
    </div>
  );
}
