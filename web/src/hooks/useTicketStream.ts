import { useEffect, useState } from "react";

import { streamTicketEvents } from "../api/chat";

export type TicketEvent = {
  event: string;
  external_id?: string;
  actor?: string;
  comment?: string;
};

const TICKET_EVENTS = ["assigned", "in_progress", "escalated", "resolved", "closed", "reopen"];

/**
 * 订阅会话工单状态 SSE（替换轮询）。返回按时间累积的工单事件列表。
 * 走 fetch（带鉴权头）而非原生 EventSource —— 后者无法携带 Bearer / X-Guest-ID，
 * 会让 C 端/游客被后端归属校验 403。断线后退避重连。
 */
export function useTicketStream(conversationId: number | null): TicketEvent[] {
  const [events, setEvents] = useState<TicketEvent[]>([]);

  useEffect(() => {
    if (conversationId == null) return;
    let stopped = false;
    void (async () => {
      while (!stopped) {
        try {
          for await (const ev of streamTicketEvents({ conversationId })) {
            if (stopped) break;
            const name = (ev as { type?: string }).type;
            if (name && TICKET_EVENTS.includes(name)) {
              const { external_id, actor, comment } = ev as unknown as TicketEvent;
              setEvents((prev) => [...prev, { event: name, external_id, actor, comment }]);
            }
          }
        } catch {
          /* 流断开，退避后重连 */
        }
        if (stopped) break;
        await new Promise((r) => setTimeout(r, 2000));
      }
    })();
    return () => {
      stopped = true;
    };
  }, [conversationId]);

  return events;
}
