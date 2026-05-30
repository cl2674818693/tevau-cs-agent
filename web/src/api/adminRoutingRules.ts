import { staffFetch } from "./staffFetch";

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export type RoutingRule = {
  id: number;
  match_type: string;
  match_value: string;
  target_group_id: number;
  priority: number;
  active: number;
  created_at: string;
};

export async function listRules(token: string): Promise<RoutingRule[]> {
  const r = await staffFetch("/admin/api/v1/routing-rules", { headers: authHeaders(token) });
  if (!r.ok) throw new Error(`list ${r.status}`);
  return (await r.json()).rules;
}

export async function createRule(
  token: string,
  body: { match_type: string; match_value: string; target_group_id: number; priority: number },
): Promise<void> {
  const r = await staffFetch("/admin/api/v1/routing-rules", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const b = await r.json().catch(() => ({}));
    throw new Error(b.detail ?? `create ${r.status}`);
  }
}

export async function setRuleActive(token: string, id: number, active: number): Promise<void> {
  const r = await staffFetch(`/admin/api/v1/routing-rules/${id}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify({ active }),
  });
  if (!r.ok) throw new Error(`patch ${r.status}`);
}

export async function deleteRule(token: string, id: number): Promise<void> {
  const r = await staffFetch(`/admin/api/v1/routing-rules/${id}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`delete ${r.status}`);
}
