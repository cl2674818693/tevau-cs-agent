import { useTranslation } from "react-i18next";

import type { TicketEvent } from "../hooks/useTicketStream";

const TICKET_KEYS = new Set([
  "assigned",
  "in_progress",
  "escalated",
  "resolved",
  "closed",
  "reopen",
]);

/** 顶部工单状态条：显示最新工单事件（实时 SSE 推送）。 */
export function TicketStatusBanner({ events }: { events: TicketEvent[] }) {
  const { t } = useTranslation();
  if (events.length === 0) return null;
  const last = events[events.length - 1];
  const label = TICKET_KEYS.has(last.event) ? t(`ticket.${last.event}`) : last.event;
  return (
    <div className="px-page py-2 glass border-b border-white/5 text-body3 text-chat-on-surface-variant">
      {label}
      {last.external_id ? ` · ${last.external_id}` : ""}
    </div>
  );
}
