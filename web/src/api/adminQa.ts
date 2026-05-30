import { staffFetch } from "./staffFetch";

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export type ScorecardItem = { key: string; label?: string; weight?: number };

export type Scorecard = {
  id: number;
  name: string;
  items_json: string;
  active: number;
  created_at: string;
};

export type QaReview = {
  id: number;
  conversation_id: number;
  reviewer_staff_id: string;
  scorecard_id: number;
  score: number;
  items_result_json: string;
  tags: string | null;
  comment: string | null;
  created_at: string;
};

export async function listScorecards(token: string, activeOnly = false): Promise<Scorecard[]> {
  const r = await staffFetch(`/admin/api/v1/qa/scorecards?active_only=${activeOnly}`, {
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`list failed ${r.status}`);
  return (await r.json()).scorecards;
}

export async function createScorecard(
  token: string,
  body: { name: string; items: ScorecardItem[] },
): Promise<void> {
  const r = await staffFetch("/admin/api/v1/qa/scorecards", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`create failed ${r.status}`);
}

export async function submitReview(
  token: string,
  body: {
    conversation_id: number;
    scorecard_id: number;
    score: number;
    items_result: Record<string, number>;
    tags?: string;
    comment?: string;
  },
): Promise<void> {
  const r = await staffFetch("/admin/api/v1/qa/reviews", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`submit failed ${r.status}`);
}

export async function listReviews(
  token: string,
  opts?: { conversation_id?: number; reviewer_staff_id?: string },
): Promise<QaReview[]> {
  const qs = new URLSearchParams();
  if (opts?.conversation_id != null) qs.set("conversation_id", String(opts.conversation_id));
  if (opts?.reviewer_staff_id) qs.set("reviewer_staff_id", opts.reviewer_staff_id);
  const r = await staffFetch(`/admin/api/v1/qa/reviews?${qs.toString()}`, {
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`reviews failed ${r.status}`);
  return (await r.json()).reviews;
}
