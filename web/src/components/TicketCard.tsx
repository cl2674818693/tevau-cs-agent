import { CheckCircle2, Ticket, XCircle } from "lucide-react";

import { Button } from "./ui/button";
import { Card } from "./ui/card";

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
    <Card className="bg-yellow-50/40">
      <div className="px-page py-block-sm space-y-1">
        <div className="flex items-center gap-2 text-body3 text-ink-subtle">
          <Ticket className="h-3.5 w-3.5" />
          <span className="font-mono">{externalId}</span>
          <span className="ml-auto">{statusLabel(status)}</span>
        </div>
        <div className="text-body1 text-ink-primary">{summary}</div>
        {status === "resolved" && (
          <div className="flex gap-2 pt-1">
            <Button size="sm" variant="primary" onClick={onConfirm}>
              <CheckCircle2 className="h-3.5 w-3.5" /> 已解决
            </Button>
            <Button size="sm" variant="ghost" onClick={onReject}>
              <XCircle className="h-3.5 w-3.5" /> 未解决
            </Button>
          </div>
        )}
      </div>
    </Card>
  );
}
