import { staffFetch } from "./staffFetch";

export type DashboardOverview = {
  total_conversations: number;
  handoff: number;
  handoff_rate: number;
  upvote: number;
  downvote: number;
  downvote_rate: number;
  tool_calls: number;
  tool_empty: number;
  tool_empty_rate: number;
  out_of_scope: number;
  failed_turns: number;
};

export async function getOverview(token: string, opts?: { from?: string }): Promise<DashboardOverview> {
  const qs = new URLSearchParams();
  if (opts?.from) qs.set("from", opts.from);
  const r = await staffFetch(`/admin/api/v1/dashboard/overview?${qs.toString()}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!r.ok) throw new Error(`overview failed ${r.status}`);
  return r.json();
}
