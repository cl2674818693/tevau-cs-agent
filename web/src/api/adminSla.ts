import { staffFetch } from "./staffFetch";

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export type SlaPolicy = {
  id: number;
  metric: string;
  threshold_seconds: number;
  scope: string;
  scope_value: string | null;
  active: number;
  created_at: string;
};

export type SlaBreach = {
  conversation_id: number;
  metric: string;
  elapsed_seconds: number;
  threshold_seconds: number;
};

export async function listPolicies(token: string): Promise<SlaPolicy[]> {
  const r = await staffFetch("/admin/api/v1/sla/policies", { headers: authHeaders(token) });
  if (!r.ok) throw new Error(`list failed ${r.status}`);
  return (await r.json()).policies;
}

export async function createPolicy(
  token: string,
  body: { metric: string; threshold_seconds: number; scope: string; scope_value?: string | null },
): Promise<void> {
  const r = await staffFetch("/admin/api/v1/sla/policies", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`create failed ${r.status}`);
}

export async function setPolicyActive(token: string, id: number, active: number): Promise<void> {
  const r = await staffFetch(`/admin/api/v1/sla/policies/${id}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify({ active }),
  });
  if (!r.ok) throw new Error(`patch failed ${r.status}`);
}

export async function deletePolicy(token: string, id: number): Promise<void> {
  const r = await staffFetch(`/admin/api/v1/sla/policies/${id}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`delete failed ${r.status}`);
}

export async function listBreaches(token: string): Promise<SlaBreach[]> {
  const r = await staffFetch("/admin/api/v1/sla/breaches", { headers: authHeaders(token) });
  if (!r.ok) throw new Error(`breaches failed ${r.status}`);
  return (await r.json()).breaches;
}
