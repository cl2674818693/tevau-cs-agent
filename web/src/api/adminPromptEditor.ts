import { staffFetch } from "./staffFetch";

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export type PromptDraft = {
  id: number;
  version: string;
  file_name: string;
  content: string;
  status: string;
  editor: string | null;
  created_at: string;
};

export async function listDrafts(token: string, version: string): Promise<PromptDraft[]> {
  const r = await staffFetch(
    `/admin/api/v1/prompt-editor?version=${encodeURIComponent(version)}`,
    { headers: authHeaders(token) },
  );
  if (!r.ok) throw new Error(`list ${r.status}`);
  return (await r.json()).drafts;
}

export async function createDraft(
  token: string, body: { version: string; file_name: string; content: string },
): Promise<{ id: number }> {
  const r = await staffFetch("/admin/api/v1/prompt-editor", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`create ${r.status}`);
  return r.json();
}

export async function publishDraft(token: string, id: number): Promise<void> {
  const r = await staffFetch(`/admin/api/v1/prompt-editor/${id}/publish`, {
    method: "POST",
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`publish ${r.status}`);
}

export async function deleteDraft(token: string, id: number): Promise<void> {
  const r = await staffFetch(`/admin/api/v1/prompt-editor/${id}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`delete ${r.status}`);
}
