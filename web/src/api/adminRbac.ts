import { staffFetch } from "./staffFetch";

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export type RbacMatrix = {
  matrix: Record<string, Record<string, boolean>>;
  roles: string[];
  permission_keys: string[];
};

export async function getMatrix(token: string): Promise<RbacMatrix> {
  const r = await staffFetch("/admin/api/v1/rbac/matrix", { headers: authHeaders(token) });
  if (!r.ok) throw new Error(`matrix ${r.status}`);
  return r.json();
}

export async function upsertMatrix(
  token: string,
  items: { role: string; permission_key: string; allowed: number }[],
): Promise<void> {
  const r = await staffFetch("/admin/api/v1/rbac/matrix", {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify({ items }),
  });
  if (!r.ok) throw new Error(`upsert ${r.status}`);
}
