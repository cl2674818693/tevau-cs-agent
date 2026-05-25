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
    <div className="bg-surface-card border border-line shadow-sm rounded-md overflow-hidden">
      <div className="flex items-center gap-2 px-page py-block-sm border-b border-line text-body3">
        <Ticket className="h-3.5 w-3.5 text-brand" />
        <span className="font-mono text-ink-secondary">{externalId}</span>
        <span className="ml-auto px-2 py-0.5 rounded-full bg-soft-warning text-status-warning text-footnote font-bold">
          {statusLabel(status)}
        </span>
      </div>
      <div className="px-page py-block-sm space-y-3">
        <div className="text-body2 text-ink">{summary}</div>
        {status === "resolved" && (
          <div className="grid grid-cols-2 gap-3">
            <button
              onClick={onConfirm}
              className="flex items-center justify-center gap-1 bg-brand text-ink-onbrand text-body3 font-bold py-2.5 rounded active:scale-95 transition-all hover:bg-brand-dark"
            >
              <CheckCircle2 className="h-3.5 w-3.5" /> 已解决
            </button>
            <button
              onClick={onReject}
              className="flex items-center justify-center gap-1 border border-line text-ink-secondary text-body3 font-bold py-2.5 rounded active:scale-95 transition-all hover:bg-surface-hover"
            >
              <XCircle className="h-3.5 w-3.5" /> 未解决
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
