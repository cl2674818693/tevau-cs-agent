export type StaffConversation = {
  id: number;
  user_type: string;
  subject_id: string;
  mode: string;
  assigned_staff_id: string | null;
  created_at: string;
  // 风险标记（后端可能返回 boolean 或 0/1，渲染时用 !!x 判断）
  has_failed?: boolean | number;
  has_out_of_scope?: boolean | number;
  has_downvote?: boolean | number;
  has_empty_tool?: boolean | number;
  needs_review?: boolean | number;
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
  riskOnly?: boolean,
): Promise<StaffConversation[]> {
  const qs = new URLSearchParams({ status });
  if (riskOnly) qs.set("risk_only", "true");
  const r = await fetch(`/staff/api/v1/conversations?${qs.toString()}`, {
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

/** 客服写操作统一 POST：失败抛错，调用方据此提示，不再静默乐观更新。 */
async function postStaff(token: string, path: string, body?: unknown): Promise<void> {
  const r = await fetch(path, {
    method: "POST",
    headers: authHeaders(token),
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`request failed ${r.status}`);
}

export async function releaseConversation(token: string, id: number): Promise<void> {
  await postStaff(token, `/staff/api/v1/conversations/${id}/release`);
}

export async function sendStaffMessage(token: string, id: number, content: string): Promise<void> {
  await postStaff(token, `/staff/api/v1/conversations/${id}/messages`, { content });
}

export async function enableAiDraft(token: string, id: number): Promise<void> {
  await postStaff(token, `/staff/api/v1/conversations/${id}/ai-draft/enable`);
}

export async function disableAiDraft(token: string, id: number): Promise<void> {
  await postStaff(token, `/staff/api/v1/conversations/${id}/ai-draft/disable`);
}

export async function approveAiDraft(token: string, id: number): Promise<void> {
  await postStaff(token, `/staff/api/v1/conversations/${id}/ai-draft/approve`);
}

export async function rejectAiDraft(token: string, id: number, rewrite: string): Promise<void> {
  await postStaff(token, `/staff/api/v1/conversations/${id}/ai-draft/reject`, { rewrite });
}

export type AiToolResult = { ok: boolean; data?: unknown; error?: string };

/** 客服代查 AI 工具（仅 senior/engineer）；结果只显示给客服。 */
export async function runAiTool(
  token: string,
  id: number,
  toolName: string,
  params: Record<string, unknown>,
): Promise<AiToolResult> {
  const r = await fetch(`/staff/api/v1/conversations/${id}/ai-tools/${toolName}`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ params }),
  });
  if (!r.ok) return { ok: false, error: `请求失败 ${r.status}` };
  return r.json();
}

export async function transferConversation(
  token: string,
  id: number,
  targetStaffId: string,
): Promise<boolean> {
  const r = await fetch(`/staff/api/v1/conversations/${id}/transfer-to/${targetStaffId}`, {
    method: "POST",
    headers: authHeaders(token),
  });
  return r.ok;
}

export async function resolveConversation(token: string, id: number): Promise<void> {
  await postStaff(token, `/staff/api/v1/conversations/${id}/resolve`);
}

export type StaffKpi = {
  staff_id: string;
  takeovers: number;
  releases: number;
  resolved: number;
  release_ratio: number;
  resolved_ratio: number;
  avg_handle_seconds: number;
};

export async function getKpi(token: string, from?: string, to?: string): Promise<StaffKpi[]> {
  const qs = new URLSearchParams();
  if (from) qs.set("from", from);
  if (to) qs.set("to", to);
  const r = await fetch(`/staff/api/v1/kpi?${qs.toString()}`, { headers: authHeaders(token) });
  if (!r.ok) throw new Error(`kpi failed ${r.status}`);
  const body = await r.json();
  return body.staff as StaffKpi[];
}

// ---- 留痕查看（只读）----

export type KnowledgeGaps = {
  out_of_scope: number;
  failed_turns: number;
  thumbs_down: number;
};

export async function getKnowledgeGaps(
  token: string,
  from?: string,
  to?: string,
): Promise<KnowledgeGaps> {
  const qs = new URLSearchParams();
  if (from) qs.set("from", from);
  if (to) qs.set("to", to);
  const r = await fetch(`/staff/api/v1/insights/knowledge-gaps?${qs.toString()}`, {
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`insights failed ${r.status}`);
  return r.json();
}

export type StaffMessage = {
  id: number;
  role: string;
  content: string;
  status: string;
  error_code: string | null;
  topic_verdict: string | null;
  created_at: string;
};

export async function getConversationMessages(token: string, id: number): Promise<StaffMessage[]> {
  const r = await fetch(`/staff/api/v1/conversations/${id}/messages`, {
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`messages failed ${r.status}`);
  return (await r.json()).messages as StaffMessage[];
}

export type ToolAudit = {
  id: number;
  conversation_id?: number;
  tool_name: string;
  params_json: string;
  result_size: number;
  duration_ms: number;
  rejected: number;
  reject_reason: string | null;
  created_at: string;
  result_count?: number;
  is_empty?: number | boolean;
  subject_id?: string;
  user_type?: string;
};

export async function getConversationAudits(token: string, id: number): Promise<ToolAudit[]> {
  const r = await fetch(`/staff/api/v1/conversations/${id}/tool-audits`, {
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`audits failed ${r.status}`);
  return (await r.json()).audits as ToolAudit[];
}

export type MessageFeedback = {
  id: number;
  message_id: number;
  rating: string;
  reason: string | null;
  created_at: string;
};

export async function getConversationFeedback(
  token: string,
  id: number,
): Promise<MessageFeedback[]> {
  const r = await fetch(`/staff/api/v1/conversations/${id}/feedback`, {
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`feedback failed ${r.status}`);
  return (await r.json()).feedback as MessageFeedback[];
}

export type RecentAuditsFilter = {
  rejectedOnly?: boolean;
  toolName?: string;
  emptyOnly?: boolean;
  conversationId?: string;
  beforeId?: number;
  limit?: number;
};

export async function getRecentAudits(
  token: string,
  filter: RecentAuditsFilter = {},
): Promise<ToolAudit[]> {
  const { rejectedOnly, toolName, emptyOnly, conversationId, beforeId, limit = 100 } = filter;
  const qs = new URLSearchParams({ limit: String(limit) });
  if (rejectedOnly) qs.set("rejected", "true");
  if (toolName) qs.set("tool_name", toolName);
  if (emptyOnly) qs.set("empty_only", "true");
  if (conversationId) qs.set("conversation_id", conversationId);
  if (beforeId != null) qs.set("before_id", String(beforeId));
  const r = await fetch(`/staff/api/v1/audits/recent?${qs.toString()}`, {
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`recent audits failed ${r.status}`);
  return (await r.json()).audits as ToolAudit[];
}

export type StaffStreamEvent = {
  type: string;
  content?: string;
  to?: string;
  draft?: string;
  name?: string; // tool_use：工具名
  input?: Record<string, unknown>; // tool_use：入参
  to_staff_id?: string; // transferred
  by_staff_id?: string; // mode_change
};

/** 取单个会话当前状态（mode/assigned_staff_id），用于详情页初始化接管态。 */
export async function getStaffConversation(token: string, id: number): Promise<StaffConversation> {
  const r = await fetch(`/staff/api/v1/conversations/${id}`, { headers: authHeaders(token) });
  if (!r.ok) throw new Error(`get conversation failed ${r.status}`);
  return r.json();
}

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
  // SSE 帧分隔符：sse-starlette 默认用 \r\n\r\n（规范也允许 \r\r / \n\n）。
  // 只认 \n\n 会导致 \r\n\r\n 永远切不出帧，staff 所有实时事件丢失。与 chat.ts 保持一致。
  const FRAME_SEP = /\r\n\r\n|\r\r|\n\n/;
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let m: RegExpExecArray | null;
    while ((m = FRAME_SEP.exec(buffer)) !== null) {
      const frame = buffer.slice(0, m.index);
      buffer = buffer.slice(m.index + m[0].length);
      const eventLine = frame.split(/\r\n|\r|\n/).find((l) => l.startsWith("event:"));
      const dataLine = frame.split(/\r\n|\r|\n/).find((l) => l.startsWith("data:"));
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
