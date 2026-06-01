import { staffFetch } from "./staffFetch";

function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}` };
}

export type StaffPerformance = {
  staff_id: string;
  takeovers: number;
  releases: number;
  resolved: number;
  transfers: number;
  release_ratio: number;
  resolved_ratio: number;
  transfer_ratio: number;
  avg_handle_seconds: number;
  satisfaction: { count: number; avg_rating: number };
  qa: { count: number; avg_score: number };
};

export type StaffKpiRow = {
  staff_id: string;
  takeovers: number;
  releases: number;
  resolved: number;
  transfers: number;
  release_ratio: number;
  resolved_ratio: number;
  transfer_ratio: number;
  avg_handle_seconds: number;
};

export type TeamPerformance = {
  from: string | null;
  to: string | null;
  team: {
    staff_count: number;
    total_takeovers: number;
    total_resolved: number;
    total_transfers: number;
    avg_handle_seconds: number;
  };
  staff: StaffKpiRow[];
};

export async function listPerformance(
  token: string,
  opts?: { from?: string; to?: string },
): Promise<TeamPerformance> {
  const qs = new URLSearchParams();
  if (opts?.from) qs.set("from", opts.from);
  if (opts?.to) qs.set("to", opts.to);
  const r = await staffFetch(
    `/admin/api/v1/staff/performance?${qs.toString()}`,
    { headers: authHeaders(token) },
  );
  if (!r.ok) throw new Error(`list performance ${r.status}`);
  return r.json();
}

export async function getPerformance(
  token: string,
  staffId: string,
  opts?: { from?: string; to?: string },
): Promise<StaffPerformance> {
  const qs = new URLSearchParams();
  if (opts?.from) qs.set("from", opts.from);
  if (opts?.to) qs.set("to", opts.to);
  const r = await staffFetch(
    `/admin/api/v1/staff/${staffId}/performance?${qs.toString()}`,
    { headers: authHeaders(token) },
  );
  if (!r.ok) throw new Error(`performance ${r.status}`);
  return r.json();
}

export type StaffConversation = {
  id: number;
  user_type: string;
  mode: string;
  status: string;
  assigned_staff_id: string | null;
  created_at: string;
  assigned_at: string | null;
};

export async function listStaffConversations(
  token: string,
  staffId: string,
  opts?: { from?: string; to?: string },
): Promise<StaffConversation[]> {
  const qs = new URLSearchParams();
  if (opts?.from) qs.set("from", opts.from);
  if (opts?.to) qs.set("to", opts.to);
  const r = await staffFetch(
    `/admin/api/v1/staff/${staffId}/conversations?${qs.toString()}`,
    { headers: authHeaders(token) },
  );
  if (!r.ok) throw new Error(`list conversations ${r.status}`);
  return (await r.json()).conversations;
}

export type StaffQaReview = {
  review_id: number;
  conv_id: number;
  scorecard_name: string | null;
  total_score: number;
  verdict: string | null;
  reviewer_staff_id: string;
  created_at: string;
};

export async function listStaffQaReviews(
  token: string,
  staffId: string,
  opts?: { from?: string; to?: string },
): Promise<StaffQaReview[]> {
  const qs = new URLSearchParams();
  if (opts?.from) qs.set("from", opts.from);
  if (opts?.to) qs.set("to", opts.to);
  const r = await staffFetch(
    `/admin/api/v1/staff/${staffId}/qa-reviews?${qs.toString()}`,
    { headers: authHeaders(token) },
  );
  if (!r.ok) throw new Error(`list qa reviews ${r.status}`);
  return (await r.json()).reviews;
}
