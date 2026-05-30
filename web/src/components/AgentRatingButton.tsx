import { useEffect, useState } from "react";

import { getRatingEligibility, submitAgentRating } from "../api/userAgentRating";

function Stars({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  return (
    <div className="flex gap-1" role="radiogroup" aria-label="评分">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          role="radio"
          aria-checked={value === n}
          onClick={() => onChange(n)}
          className={value >= n ? "text-status-warning" : "text-ink-tertiary"}
        >
          ★
        </button>
      ))}
    </div>
  );
}

function RatingDialog({
  onClose,
  onDone,
  conversationId,
}: {
  onClose: () => void;
  onDone: () => void;
  conversationId: number;
}) {
  const [rating, setRating] = useState(5);
  const [comment, setComment] = useState("");
  const [err, setErr] = useState("");
  async function submit() {
    setErr("");
    try {
      await submitAgentRating(conversationId, { rating, comment: comment || undefined });
      onDone();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "提交失败");
    }
  }
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/30"
      onClick={onClose}
    >
      <div
        className="w-80 rounded-md bg-surface-card p-4 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-2 text-sh2 text-ink-primary">评价本次客服</div>
        <Stars value={rating} onChange={setRating} />
        <textarea
          className="mt-2 w-full rounded border border-line px-2 py-1 text-body3"
          rows={3}
          placeholder="留言（可选）"
          value={comment}
          onChange={(e) => setComment(e.target.value)}
        />
        {err && <div className="mt-1 text-footnote text-status-error">{err}</div>}
        <div className="mt-3 flex justify-end gap-2">
          <button onClick={onClose} className="rounded px-3 py-1 text-body3 text-ink-secondary">
            取消
          </button>
          <button
            onClick={submit}
            className="rounded bg-brand px-3 py-1 text-body3 text-ink-onbrand"
          >
            提交
          </button>
        </div>
      </div>
    </div>
  );
}

export function AgentRatingButton({ conversationId }: { conversationId: number | null }) {
  const [eligible, setEligible] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (conversationId == null || conversationId <= 0) return;
    let cancelled = false;
    getRatingEligibility(conversationId)
      .then((e) => {
        if (!cancelled) setEligible(e.eligible && !e.already_rated);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [conversationId]);

  if (!eligible || conversationId == null) return null;
  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-20 right-4 rounded-full bg-brand px-3 py-2 text-body3 text-ink-onbrand shadow-md md:bottom-6"
        aria-label="评价客服"
      >
        评价客服
      </button>
      {open && (
        <RatingDialog
          conversationId={conversationId}
          onClose={() => setOpen(false)}
          onDone={() => {
            setOpen(false);
            setEligible(false);
          }}
        />
      )}
    </>
  );
}
