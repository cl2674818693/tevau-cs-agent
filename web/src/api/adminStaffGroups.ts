import { staffFetch } from "./staffFetch";

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export type StaffGroup = {
  id: number;
  name: string;
  description: string | null;
  active: number;
  created_at: string;
};

export async function listGroups(token: string): Promise<StaffGroup[]> {
  const r = await staffFetch("/admin/api/v1/staff-groups", { headers: authHeaders(token) });
  if (!r.ok) throw new Error(`list ${r.status}`);
  return (await r.json()).groups;
}

export async function createGroup(
  token: string, body: { name: string; description?: string },
): Promise<void> {
  const r = await staffFetch("/admin/api/v1/staff-groups", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`create ${r.status}`);
}

export async function patchGroup(
  token: string, id: number,
  body: { name?: string; description?: string; active?: number },
): Promise<void> {
  const r = await staffFetch(`/admin/api/v1/staff-groups/${id}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`patch ${r.status}`);
}

export async function deleteGroup(token: string, id: number): Promise<void> {
  const r = await staffFetch(`/admin/api/v1/staff-groups/${id}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`delete ${r.status}`);
}
