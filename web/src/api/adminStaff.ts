import { staffFetch } from "./staffFetch";

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export type StaffRow = {
  id: number;
  staff_id: string;
  display_name: string;
  role: string;
  active: number;
  created_at: string;
};

export async function listStaff(token: string): Promise<StaffRow[]> {
  const r = await staffFetch("/admin/api/v1/staff", { headers: authHeaders(token) });
  if (!r.ok) throw new Error(`list failed ${r.status}`);
  return (await r.json()).staff as StaffRow[];
}

export async function createStaff(
  token: string,
  body: { staff_id: string; display_name: string; role: string; password: string },
): Promise<void> {
  const r = await staffFetch("/admin/api/v1/staff", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const b = await r.json().catch(() => ({}));
    throw new Error(b.detail ?? `create failed ${r.status}`);
  }
}

export async function patchStaff(
  token: string,
  staffId: string,
  body: { display_name?: string; role?: string; active?: number },
): Promise<void> {
  const r = await staffFetch(`/admin/api/v1/staff/${staffId}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`patch failed ${r.status}`);
}

export async function resetPassword(token: string, staffId: string, password: string): Promise<void> {
  const r = await staffFetch(`/admin/api/v1/staff/${staffId}/reset-password`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ password }),
  });
  if (!r.ok) throw new Error(`reset failed ${r.status}`);
}

export const STAFF_ROLES = ["agent", "senior", "supervisor", "engineer", "manager", "admin"];
