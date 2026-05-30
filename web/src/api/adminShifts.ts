import { staffFetch } from "./staffFetch";

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export type Shift = {
  id: number;
  staff_id: string;
  start_at: string;
  end_at: string;
  created_at: string;
};

export async function listShifts(
  token: string, opts?: { staff_id?: string; from?: string; to?: string },
): Promise<Shift[]> {
  const qs = new URLSearchParams();
  if (opts?.staff_id) qs.set("staff_id", opts.staff_id);
  if (opts?.from) qs.set("from", opts.from);
  if (opts?.to) qs.set("to", opts.to);
  const r = await staffFetch(`/admin/api/v1/shifts?${qs.toString()}`, {
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`list ${r.status}`);
  return (await r.json()).shifts;
}

export async function createShift(
  token: string, body: { staff_id: string; start_at: string; end_at: string },
): Promise<void> {
  const r = await staffFetch("/admin/api/v1/shifts", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`create ${r.status}`);
}

export async function deleteShift(token: string, id: number): Promise<void> {
  const r = await staffFetch(`/admin/api/v1/shifts/${id}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`delete ${r.status}`);
}
