import { CheckCircle2, Ticket, XCircle } from "lucide-react";

function statusLabel(s: string) {
  return (
    {
      pending: "等待受理",
      assigned: "已分派",
      in_progress: "处理中",
      resolved: "已处理",
      closed: "已关闭",
    }[s] ?? s
  );
}

export function TicketCard({
  externalId,
  summary,
  status = "pending",
  onConfirm,
  onReject,
}: {
  externalId: string;
  summary: string;
  status?: "pending" | "assigned" | "in_progress" | "resolved" | "closed";
  onConfirm?: () => void;
  onReject?: () => void;
}) {
  return (
    <div className="glass cyan-glow-border rounded-xl overflow-hidden relative">
      <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-chat-primary/40 to-transparent" />
      <div className="flex items-center gap-2 px-page py-block-sm border-b border-white/5 bg-white/5 text-body3">
        <Ticket className="h-3.5 w-3.5 text-chat-primary" />
        <span className="font-mono text-chat-on-surface-variant">{externalId}</span>
        <span className="ml-auto px-2 py-0.5 rounded-full bg-chat-primary/10 text-chat-primary text-footnote font-bold border border-chat-primary/20">
          {statusLabel(status)}
        </span>
      </div>
      <div className="px-page py-block-sm space-y-3">
        <div className="text-body2 text-chat-on-surface/90">{summary}</div>
        {status === "resolved" && (
          <div className="grid grid-cols-2 gap-3">
            <button
              onClick={onConfirm}
              className="flex items-center justify-center gap-1 bg-chat-primary text-chat-on-primary text-body3 font-bold py-2.5 rounded-lg active:scale-95 transition-all"
            >
              <CheckCircle2 className="h-3.5 w-3.5" /> 已解决
            </button>
            <button
              onClick={onReject}
              className="flex items-center justify-center gap-1 border border-chat-on-surface-variant/30 text-chat-on-surface-variant text-body3 font-bold py-2.5 rounded-lg active:scale-95 transition-all hover:bg-white/5"
            >
              <XCircle className="h-3.5 w-3.5" /> 未解决
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
