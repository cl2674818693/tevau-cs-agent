export type RatingEligibility = {
  eligible: boolean;
  already_rated: boolean;
  staff_id: string | null;
};

/** 走默认 fetch（不用 staffFetch，因为这是 C/B 端用户接口，不是 staff token）。
 * 401 不自动登出（C 端有自己的登录引导路径）。 */
export async function getRatingEligibility(conversationId: number): Promise<RatingEligibility> {
  const r = await fetch(`/api/v1/conversations/${conversationId}/agent-rating/eligibility`, {
    credentials: "include",
  });
  if (!r.ok) throw new Error(`eligibility ${r.status}`);
  return r.json();
}

export async function submitAgentRating(
  conversationId: number,
  body: { rating: number; comment?: string },
): Promise<void> {
  const r = await fetch(`/api/v1/conversations/${conversationId}/agent-rating`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const b = await r.json().catch(() => ({}));
    throw new Error(b.detail ?? `rate ${r.status}`);
  }
}
