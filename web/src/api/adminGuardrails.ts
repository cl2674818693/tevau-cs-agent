import { staffFetch } from "./staffFetch";

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export type Guardrail = {
  id: number;
  type: string;
  pattern: string;
  action: string;
  active: number;
  created_by: string | null;
  created_at: string;
};

export async function listGuardrails(token: string): Promise<Guardrail[]> {
  const r = await staffFetch("/admin/api/v1/guardrails", { headers: authHeaders(token) });
  if (!r.ok) throw new Error(`list ${r.status}`);
  return (await r.json()).rules;
}

export async function createGuardrail(
  token: string, body: { type: string; pattern: string; action: string },
): Promise<void> {
  const r = await staffFetch("/admin/api/v1/guardrails", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const b = await r.json().catch(() => ({}));
    throw new Error(b.detail ?? `create ${r.status}`);
  }
}

export async function setGuardrailActive(token: string, id: number, active: number): Promise<void> {
  const r = await staffFetch(`/admin/api/v1/guardrails/${id}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify({ active }),
  });
  if (!r.ok) throw new Error(`patch ${r.status}`);
}

export async function patchGuardrail(
  token: string,
  id: number,
  body: { type?: string; pattern?: string; action?: string },
): Promise<Guardrail> {
  const r = await staffFetch(`/admin/api/v1/guardrails/${id}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const b = await r.json().catch(() => ({}));
    throw new Error(b.detail ?? `patch ${r.status}`);
  }
  return r.json();
}

export async function deleteGuardrail(token: string, id: number): Promise<void> {
  const r = await staffFetch(`/admin/api/v1/guardrails/${id}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`delete ${r.status}`);
}
