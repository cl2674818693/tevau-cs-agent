import { staffFetch } from "./staffFetch";

export type AuditEntry = {
  id: number;
  actor: string;
  action: string;
  target_type: string | null;
  target_id: string | null;
  detail_json: string | null;
  created_at: string;
};

export async function listAudit(
  token: string,
  opts?: { actor?: string; action?: string },
): Promise<AuditEntry[]> {
  const qs = new URLSearchParams();
  if (opts?.actor) qs.set("actor", opts.actor);
  if (opts?.action) qs.set("action", opts.action);
  const r = await staffFetch(`/admin/api/v1/audit?${qs.toString()}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!r.ok) throw new Error(`audit failed ${r.status}`);
  return (await r.json()).entries;
}
