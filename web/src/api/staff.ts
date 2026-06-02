import { staffFetch } from "./staffFetch";

export type StaffConversation = {
  id: number;
  user_type: string;
  subject_id: string;
  mode: string;
  assigned_staff_id: string | null;
  /** 仅 get_meta_with_risk 返回；list_for_staff 不带（旧 SQL 未 SELECT）。null 表示从未接管过。 */
  assigned_at?: string | null;
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
  // 登录用裸 fetch：此处 401 表示账号/密码错误，不能走 staffFetch 的会话过期跳转。
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
  const r = await staffFetch(`/staff/api/v1/conversations?${qs.toString()}`, {
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`list failed ${r.status}`);
  return r.json();
}

/** 接管：成功 true；被他人抢占（409）返回 false。 */
export async function takeConversation(token: string, id: number): Promise<boolean> {
  const r = await staffFetch(`/staff/api/v1/conversations/${id}/take`, {
    method: "POST",
    headers: authHeaders(token),
  });
  return r.ok;
}

/** 客服写操作统一 POST：失败抛错，调用方据此提示，不再静默乐观更新。 */
async function postStaff(token: string, path: string, body?: unknown): Promise<void> {
  const r = await staffFetch(path, {
    method: "POST",
    headers: authHeaders(token),
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`request failed ${r.status}`);
}

export async function releaseConversation(token: string, id: number): Promise<void> {
  await postStaff(token, `/staff/api/v1/conversations/${id}/release`);
}

export async function sendStaffMessage(
  token: string,
  id: number,
  content: string,
  attachmentIds: number[] = [],
): Promise<void> {
  await postStaff(token, `/staff/api/v1/conversations/${id}/messages`, {
    content,
    attachment_ids: attachmentIds,
  });
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
  const r = await staffFetch(`/staff/api/v1/conversations/${id}/ai-tools/${toolName}`, {
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
  const r = await staffFetch(`/staff/api/v1/conversations/${id}/transfer-to/${targetStaffId}`, {
    method: "POST",
    headers: authHeaders(token),
  });
  return r.ok;
}

export type TransferCandidate = {
  staff_id: string;
  display_name: string;
  role: string;
};

export type SubjectInfo = {
  subject: {
    user_type: string;
    subject_id: string;
    found: boolean;
    // C 端
    user_id?: number;
    user_code?: string;
    nick_name?: string;
    email?: string;
    phone?: string;
    user_status?: string;
    kyc_status?: string;
    open_card_status?: string;
    registration_time?: string;
    last_login_time?: string;
    recent_30d_transactions?: { currency: string; count: number; amount: string }[];
    // B 端
    tenant_id?: string;
    company_name?: string;
    status?: string;
  };
  client_info: {
    platform: string | null;
    app_version: string | null;
    user_agent: string | null;
    updated_at: string;
  } | null;
};

export async function getSubjectInfo(token: string, convId: number): Promise<SubjectInfo> {
  const r = await staffFetch(`/staff/api/v1/conversations/${convId}/subject-info`, {
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`subject-info failed ${r.status}`);
  return r.json();
}

export async function listTransferCandidates(token: string): Promise<TransferCandidate[]> {
  const r = await staffFetch("/staff/api/v1/transfer-candidates", {
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`transfer candidates failed ${r.status}`);
  return ((await r.json()).candidates ?? []) as TransferCandidate[];
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
  transfers?: number;
  transfer_ratio?: number;
};

export type AiQuality = {
  total_conversations: number;
  handoff: number;
  handoff_rate: number;
  upvote: number;
  downvote: number;
  downvote_rate: number;
  tool_calls: number;
  tool_empty: number;
  tool_empty_rate: number;
  out_of_scope: number;
  failed_turns: number;
};

export type KpiResult = {
  from: string | null;
  to: string | null;
  staff: StaffKpi[];
  ai_quality: AiQuality;
};

export async function getKpi(token: string, opts?: { from?: string; to?: string }): Promise<KpiResult> {
  const qs = new URLSearchParams();
  if (opts?.from) qs.set("from", opts.from);
  if (opts?.to) qs.set("to", opts.to);
  const r = await staffFetch(`/staff/api/v1/kpi?${qs.toString()}`, { headers: authHeaders(token) });
  if (!r.ok) throw new Error(`kpi failed ${r.status}`);
  const body = await r.json();
  return body as KpiResult;
}

// ---- 留痕查看（只读）----

export type KnowledgeGaps = {
  out_of_scope: number;
  failed_turns: number;
  thumbs_down: number;
  human_handoff: number;
};

export type InsightsRange = { from?: string; to?: string };

export async function getKnowledgeGaps(
  token: string,
  range: InsightsRange = {},
): Promise<KnowledgeGaps> {
  const qs = new URLSearchParams();
  if (range.from) qs.set("from", range.from);
  if (range.to) qs.set("to", range.to);
  const r = await staffFetch(`/staff/api/v1/insights/knowledge-gaps?${qs.toString()}`, {
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`insights failed ${r.status}`);
  return r.json();
}

export type ToolHealth = {
  tool_name: string;
  calls: number;
  empty: number;
  rejected: number;
  empty_rate: number;
};

export async function getToolHealth(
  token: string,
  range: InsightsRange = {},
): Promise<ToolHealth[]> {
  const qs = new URLSearchParams();
  if (range.from) qs.set("from", range.from);
  if (range.to) qs.set("to", range.to);
  const r = await staffFetch(`/staff/api/v1/insights/tool-health?${qs.toString()}`, {
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`tool-health failed ${r.status}`);
  return ((await r.json()).tools ?? []) as ToolHealth[];
}

export type GapKind = "out_of_scope" | "failed" | "thumbs_down" | "human_handoff";

export type GapConversation = {
  conversation_id: number;
  last_at: string;
};

export async function getGapConversations(
  token: string,
  kind: GapKind,
  range: InsightsRange & { limit?: number } = {},
): Promise<GapConversation[]> {
  const qs = new URLSearchParams({ kind });
  if (range.from) qs.set("from", range.from);
  if (range.to) qs.set("to", range.to);
  if (range.limit != null) qs.set("limit", String(range.limit));
  const r = await staffFetch(`/staff/api/v1/insights/gap-conversations?${qs.toString()}`, {
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`gap-conversations failed ${r.status}`);
  return ((await r.json()).conversations ?? []) as GapConversation[];
}

export type StaffMessage = {
  id: number;
  role: string;
  content: string;
  status: string;
  error_code: string | null;
  topic_verdict: string | null;
  created_at: string;
  attachments?: { id: number; mime: string }[];
};

export type MessagesPage = { messages: StaffMessage[]; hasMore: boolean };

/** 留痕消息分页：默认取最新一页；往上"加载更早"传 beforeId=当前最旧消息 id。 */
export async function getConversationMessages(
  token: string,
  id: number,
  opts: { limit?: number; beforeId?: number } = {},
): Promise<MessagesPage> {
  const qs = new URLSearchParams({ limit: String(opts.limit ?? 50) });
  if (opts.beforeId != null) qs.set("before_id", String(opts.beforeId));
  const r = await staffFetch(`/staff/api/v1/conversations/${id}/messages?${qs.toString()}`, {
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`messages failed ${r.status}`);
  const data = await r.json();
  return { messages: data.messages as StaffMessage[], hasMore: Boolean(data.has_more) };
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
  const r = await staffFetch(`/staff/api/v1/conversations/${id}/tool-audits`, {
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
  const r = await staffFetch(`/staff/api/v1/conversations/${id}/feedback`, {
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
  page?: number;
  limit?: number;
};

export type RecentAuditsPage = {
  audits: ToolAudit[];
  total: number;
  page: number;
  limit: number;
};

function buildRecentAuditsQuery(filter: RecentAuditsFilter): URLSearchParams {
  const { rejectedOnly, toolName, emptyOnly, conversationId, page = 1, limit = 100 } = filter;
  const qs = new URLSearchParams({ limit: String(limit), page: String(page) });
  if (rejectedOnly) qs.set("rejected", "true");
  if (toolName) qs.set("tool_name", toolName);
  if (emptyOnly) qs.set("empty_only", "true");
  if (conversationId) qs.set("conversation_id", conversationId);
  return qs;
}

/** 跨会话工具审计：页码式分页（page 1 基），返回 total 供页码导航。 */
export async function getRecentAudits(
  token: string,
  filter: RecentAuditsFilter = {},
): Promise<RecentAuditsPage> {
  const qs = buildRecentAuditsQuery(filter);
  const r = await staffFetch(`/staff/api/v1/audits/recent?${qs.toString()}`, {
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`recent audits failed ${r.status}`);
  const data = await r.json();
  return {
    audits: data.audits as ToolAudit[],
    total: Number(data.total ?? 0),
    page: Number(data.page ?? filter.page ?? 1),
    limit: Number(data.limit ?? filter.limit ?? 100),
  };
}

// ---- 运营只读工单列表（外部事项中心是状态真源，本地仅只读镜像）----

export type TicketStatus = "pending" | "in_progress" | "resolved" | "closed";

export type Ticket = {
  external_id: string;
  category: string | null;
  severity: string | null;
  conversation_id: number;
  created_at: string;
  status: TicketStatus;
  closed: boolean;
};

export type ListTicketsFilter = {
  open?: boolean;
  severity?: string;
  category?: string;
  beforeId?: string;
  limit?: number;
};

export async function listTickets(
  token: string,
  filter: ListTicketsFilter = {},
): Promise<Ticket[]> {
  const { open, severity, category, beforeId, limit = 50 } = filter;
  const qs = new URLSearchParams({ limit: String(limit) });
  if (open) qs.set("open", "true");
  if (severity) qs.set("severity", severity);
  if (category) qs.set("category", category);
  if (beforeId) qs.set("before_id", beforeId);
  const r = await staffFetch(`/staff/api/v1/tickets?${qs.toString()}`, {
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`list tickets failed ${r.status}`);
  return (await r.json()).tickets as Ticket[];
}

export type StaffStreamEvent = {
  type: string;
  content?: string;
  to?: string;
  draft?: string;
  name?: string; // tool_use：工具名
  input?: Record<string, unknown>; // tool_use：入参
  ok?: boolean; // tool_result：调用是否成功
  result_count?: number; // tool_result：返回条数
  empty?: boolean; // tool_result：是否查空
  to_staff_id?: string; // transferred
  by_staff_id?: string; // mode_change
  attachments?: { id: number; mime: string }[]; // user_message / human_message 带图
};

/** 取单个会话当前状态（mode/assigned_staff_id），用于详情页初始化接管态。 */
export async function getStaffConversation(token: string, id: number): Promise<StaffConversation> {
  const r = await staffFetch(`/staff/api/v1/conversations/${id}`, { headers: authHeaders(token) });
  if (!r.ok) throw new Error(`get conversation failed ${r.status}`);
  return r.json();
}

/** 订阅会话事件总线（user_message / human_message / mode_change）。带 Bearer，故用 fetch-stream。 */
export function streamStaffEvents(
  token: string,
  id: number,
  signal?: AbortSignal,
): AsyncGenerator<StaffStreamEvent> {
  return streamSse(`/staff/api/v1/conversations/${id}/stream`, token, signal);
}

/** 旁观订阅（senior/engineer）：只读看 AI 处理过程，不接管。 */
export function streamSpectateEvents(
  token: string,
  id: number,
  signal?: AbortSignal,
): AsyncGenerator<StaffStreamEvent> {
  return streamSse(`/staff/api/v1/conversations/${id}/spectate-stream`, token, signal);
}

async function* streamSse(
  url: string,
  token: string,
  signal?: AbortSignal,
): AsyncGenerator<StaffStreamEvent> {
  const resp = await staffFetch(url, { headers: { Authorization: `Bearer ${token}` }, signal });
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
