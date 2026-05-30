import { staffFetch } from "./staffFetch";

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export type KnowledgeEntry = {
  id: number;
  type: string;
  key: string;
  title: string;
  locale: string;
  status: string;
  source_gap_signal: string | null;
  created_by: string | null;
  updated_at: string;
};

export async function listKnowledge(
  token: string, opts?: { type?: string; status?: string },
): Promise<KnowledgeEntry[]> {
  const qs = new URLSearchParams();
  if (opts?.type) qs.set("type", opts.type);
  if (opts?.status) qs.set("status", opts.status);
  const r = await staffFetch(`/admin/api/v1/knowledge?${qs.toString()}`, {
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`list ${r.status}`);
  return (await r.json()).entries;
}

export async function createKnowledge(
  token: string,
  body: { type: string; key: string; title: string; content: string; locale?: string },
): Promise<{ id: number }> {
  const r = await staffFetch("/admin/api/v1/knowledge", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const b = await r.json().catch(() => ({}));
    throw new Error(b.detail ?? `create ${r.status}`);
  }
  return r.json();
}

export async function publishKnowledge(token: string, id: number): Promise<void> {
  const r = await staffFetch(`/admin/api/v1/knowledge/${id}/publish`, {
    method: "POST",
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`publish ${r.status}`);
}

export async function deleteKnowledge(token: string, id: number): Promise<void> {
  const r = await staffFetch(`/admin/api/v1/knowledge/${id}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`delete ${r.status}`);
}
