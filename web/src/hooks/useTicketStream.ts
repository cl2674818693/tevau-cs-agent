import { useEffect, useState } from "react";

export type TicketEvent = {
  event: string;
  external_id?: string;
  actor?: string;
  comment?: string;
};

const TICKET_EVENTS = ["assigned", "in_progress", "escalated", "resolved", "closed", "reopen"];

function safeParse(raw: string): Record<string, unknown> {
  try {
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

/** 订阅会话工单状态 SSE（替换轮询）。返回按时间累积的工单事件列表。 */
export function useTicketStream(conversationId: number | null): TicketEvent[] {
  const [events, setEvents] = useState<TicketEvent[]>([]);

  useEffect(() => {
    if (conversationId == null || typeof EventSource === "undefined") return;
    const sse = new EventSource(`/api/v1/conversations/${conversationId}/ticket-events-stream`);
    for (const name of TICKET_EVENTS) {
      sse.addEventListener(name, ((e: MessageEvent) => {
        setEvents((prev) => [...prev, { event: name, ...safeParse(e.data) }]);
      }) as EventListener);
    }
    return () => sse.close();
  }, [conversationId]);

  return events;
}
