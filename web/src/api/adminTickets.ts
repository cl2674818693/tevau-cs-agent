import { staffFetch } from "./staffFetch";

export type TicketEvent = {
  event: string;
  actor: string | null;
  comment: string | null;
  created_at: string;
};

export type TicketDetail = {
  external_id: string;
  conversation_id: number;
  payload_json: string;
  current_severity: string | null;
  created_at: string;
  events: TicketEvent[];
};

export async function getTicketDetail(token: string, externalId: string): Promise<TicketDetail> {
  const r = await staffFetch(`/staff/api/v1/tickets/${externalId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (r.status === 404) throw new Error("工单不存在");
  if (!r.ok) throw new Error(`ticket failed ${r.status}`);
  return r.json();
}
