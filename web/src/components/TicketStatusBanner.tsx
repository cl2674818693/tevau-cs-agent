import type { TicketEvent } from "../hooks/useTicketStream";

const LABELS: Record<string, string> = {
  assigned: "工单已受理",
  in_progress: "工单处理中",
  escalated: "工单已升级",
  resolved: "工单已解决",
  closed: "工单已关闭",
  reopen: "工单已重开",
};

/** 顶部工单状态条：显示最新工单事件（实时 SSE 推送）。 */
export function TicketStatusBanner({ events }: { events: TicketEvent[] }) {
  if (events.length === 0) return null;
  const last = events[events.length - 1];
  return (
    <div className="px-page py-2 bg-fill-secondary text-body3 text-ink-secondary border-b border-line">
      {LABELS[last.event] ?? last.event}
      {last.external_id ? ` · ${last.external_id}` : ""}
    </div>
  );
}
