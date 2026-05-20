export type StaffConversation = {
  id: number;
  user_type: string;
  subject_id: string;
  mode: string;
  assigned_staff_id: string | null;
  created_at: string;
};

export type StaffInfo = { staff_id: string; display_name: string; role: string };

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export async function staffLogin(
  staffId: string,
  password: string,
): Promise<{ token: string; staff: StaffInfo }> {
  const r = await fetch("/staff/api/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ staff_id: staffId, password }),
  });
  if (!r.ok) throw new Error("invalid credentials");
  return r.json();
}

export async function listStaffConversations(
  token: string,
  status: string,
): Promise<StaffConversation[]> {
  const r = await fetch(`/staff/api/v1/conversations?status=${encodeURIComponent(status)}`, {
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`list failed ${r.status}`);
  return r.json();
}

/** 接管：成功 true；被他人抢占（409）返回 false。 */
export async function takeConversation(token: string, id: number): Promise<boolean> {
  const r = await fetch(`/staff/api/v1/conversations/${id}/take`, {
    method: "POST",
    headers: authHeaders(token),
  });
  return r.ok;
}

export async function releaseConversation(token: string, id: number): Promise<void> {
  await fetch(`/staff/api/v1/conversations/${id}/release`, {
    method: "POST",
    headers: authHeaders(token),
  });
}

export async function sendStaffMessage(token: string, id: number, content: string): Promise<void> {
  await fetch(`/staff/api/v1/conversations/${id}/messages`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ content }),
  });
}

export async function enableAiDraft(token: string, id: number): Promise<void> {
  await fetch(`/staff/api/v1/conversations/${id}/ai-draft/enable`, {
    method: "POST",
    headers: authHeaders(token),
  });
}

export async function disableAiDraft(token: string, id: number): Promise<void> {
  await fetch(`/staff/api/v1/conversations/${id}/ai-draft/disable`, {
    method: "POST",
    headers: authHeaders(token),
  });
}

export async function approveAiDraft(token: string, id: number): Promise<void> {
  await fetch(`/staff/api/v1/conversations/${id}/ai-draft/approve`, {
    method: "POST",
    headers: authHeaders(token),
  });
}

export async function rejectAiDraft(token: string, id: number, rewrite: string): Promise<void> {
  await fetch(`/staff/api/v1/conversations/${id}/ai-draft/reject`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ rewrite }),
  });
}

export type StaffStreamEvent = {
  type: string;
  content?: string;
  to?: string;
  draft?: string;
};

/** 订阅会话事件总线（user_message / human_message / mode_change）。带 Bearer，故用 fetch-stream。 */
export function streamStaffEvents(token: string, id: number): AsyncGenerator<StaffStreamEvent> {
  return streamSse(`/staff/api/v1/conversations/${id}/stream`, token);
}

/** 旁观订阅（senior/engineer）：只读看 AI 处理过程，不接管。 */
export function streamSpectateEvents(token: string, id: number): AsyncGenerator<StaffStreamEvent> {
  return streamSse(`/staff/api/v1/conversations/${id}/spectate-stream`, token);
}

async function* streamSse(url: string, token: string): AsyncGenerator<StaffStreamEvent> {
  const resp = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
  if (!resp.ok || !resp.body) throw new Error(`stream failed ${resp.status}`);
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      const eventLine = frame.split("\n").find((l) => l.startsWith("event:"));
      const dataLine = frame.split("\n").find((l) => l.startsWith("data:"));
      if (!eventLine || !dataLine) continue;
      try {
        const data = JSON.parse(dataLine.slice("data:".length).trim());
        yield { type: eventLine.slice("event:".length).trim(), ...data };
      } catch {
        /* ignore */
      }
    }
  }
}
