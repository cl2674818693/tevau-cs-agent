import { useEffect, useState } from "react";

import { getRatingEligibility, submitAgentRating } from "../api/userAgentRating";
import type { TicketEvent } from "../hooks/useTicketStream";

const RESOLVED_EVENTS = new Set(["resolved", "closed"]);

type Props = {
  convId: number | null;
  ticketEvents: TicketEvent[];
};

/** 服务结束（最近 ticket_event 为 resolved/closed）时被动弹满意度。
 *  仅在 eligibility.eligible && !already_rated 时弹出；用户提交评分或点"稍后"即关闭。 */
export function AgentRatingPromptToast({ convId, ticketEvents }: Props) {
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (convId == null) return;
    const latest = ticketEvents[ticketEvents.length - 1];
    if (!latest || !RESOLVED_EVENTS.has(latest.event)) return;
    getRatingEligibility(convId)
      .then((el) => {
        if (el.eligible && !el.already_rated) setOpen(true);
      })
      .catch(() => {});
  }, [convId, ticketEvents]);

  if (!open || convId == null) return null;

  const onRate = async (n: number) => {
    if (submitting) return;
    setSubmitting(true);
    try {
      await submitAgentRating(convId, { rating: n });
    } catch {
      // 静默：弹窗本就是被动可关闭
    }
    setOpen(false);
    setSubmitting(false);
  };

  return (
    <div className="fixed bottom-4 right-4 z-50 w-80 rounded-md bg-surface-card p-3 shadow-lg">
      <div className="mb-2 text-body2 text-ink-primary">服务已结束，请评价本次客服</div>
      <div className="flex gap-1 mb-2">
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            disabled={submitting}
            onClick={() => void onRate(n)}
            className="text-status-warning text-lg disabled:opacity-50"
            aria-label={`${n} 星`}
          >
            ★
          </button>
        ))}
      </div>
      <button
        onClick={() => setOpen(false)}
        disabled={submitting}
        className="text-footnote text-ink-secondary"
      >
        稍后再说
      </button>
    </div>
  );
}
