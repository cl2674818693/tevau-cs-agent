import { staffFetch } from "./staffFetch";

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export type PresenceStatus = "online" | "offline";

export async function postPresence(
  token: string,
  status: PresenceStatus,
): Promise<{ ok: boolean; released_count: number }> {
  const r = await staffFetch("/staff/api/v1/presence", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ status }),
  });
  if (!r.ok) throw new Error(`presence ${status} failed: ${r.status}`);
  const body = await r.json();
  return { ok: !!body.ok, released_count: Number(body.released_count ?? 0) };
}

export type Presence = {
  staff_id: string;
  status: string;
  last_seen_at: string;
};

export async function sendHeartbeat(token: string, status: "online" | "away" = "online"): Promise<void> {
  const r = await staffFetch("/staff/api/v1/presence", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ status }),
  });
  if (!r.ok) throw new Error(`heartbeat ${r.status}`);
}

export async function listPresence(token: string): Promise<{ all: Presence[]; active: Presence[] }> {
  const r = await staffFetch("/admin/api/v1/presence", { headers: authHeaders(token) });
  if (!r.ok) throw new Error(`presence ${r.status}`);
  return r.json();
}
