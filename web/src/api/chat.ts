import type { ChatEvent, ConversationInit } from "../types";
import { authHeaders } from "./identity";

/** 统一 fetch：注入鉴权头（C=Bearer / B=X-BU-ID）+ 带 cookie（B 端 session）。 */
async function authedFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const auth = await authHeaders();
  return fetch(input, {
    ...init,
    credentials: "include",
    headers: { ...(init.headers ?? {}), ...auth },
  });
}

/**
 * 会话初始化（spec §6.2）。首屏调一次，拿 user_type / display_name / greeting / limits。
 */
export async function initConversation(): Promise<ConversationInit> {
  const resp = await authedFetch("/api/v1/conversations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  if (!resp.ok) throw new Error(`init http ${resp.status}`);
  return resp.json();
}

/** 解析一个 SSE frame → ChatEvent；ping / 解析失败返回 null。 */
function parseSseFrame(frame: string): ChatEvent | null {
  const lines = frame.split("\n");
  const eventLine = lines.find((l) => l.startsWith("event:"));
  const dataLine = lines.find((l) => l.startsWith("data:"));
  const idLine = lines.find((l) => l.startsWith("id:"));
  if (!eventLine || !dataLine) return null;
  const eventName = eventLine.slice("event:".length).trim();
  if (eventName === "ping") return null; // 心跳直接跳过
  try {
    const data = JSON.parse(dataLine.slice("data:".length).trim());
    return { type: eventName, ...data, _eventId: idLine?.slice("id:".length).trim() } as ChatEvent;
  } catch {
    return null;
  }
}

/**
 * SSE 主链路（spec §3.3）。GET 请求 + 携带 Last-Event-ID（断线重连后由 caller 传入）。
 */
export async function* streamChat(args: {
  conversationId: number;
  message: string;
  lastEventId?: string;
  clientMessageId?: string;
}): AsyncGenerator<ChatEvent> {
  let url = `/api/v1/chat?conversation_id=${args.conversationId}&message=${encodeURIComponent(
    args.message,
  )}`;
  // 幂等键：重发/重连时同 id 命中后端会重放历史回复，不重复跑 LLM
  if (args.clientMessageId) url += `&client_message_id=${encodeURIComponent(args.clientMessageId)}`;
  const headers: Record<string, string> = {};
  if (args.lastEventId) headers["Last-Event-ID"] = args.lastEventId;
  const resp = await authedFetch(url, { headers });
  if (!resp.ok || !resp.body) throw new Error(`chat http ${resp.status}`);
  yield* readSseStream(resp);
}

/** 消息级反馈（👍/👎）。messageId 为该回复在消息列表中的序号（后端仅作关联记录）。 */
export async function sendFeedback(
  conversationId: number,
  messageId: number,
  rating: "up" | "down",
  reason?: string,
): Promise<void> {
  await authedFetch(`/api/v1/conversations/${conversationId}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message_id: messageId, rating, reason }),
  });
}

/** 读取一个 SSE 响应体，逐 frame 解析成 ChatEvent。 */
async function* readSseStream(resp: Response): AsyncGenerator<ChatEvent> {
  if (!resp.body) return;
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
      const ev = parseSseFrame(frame);
      if (ev) yield ev;
    }
  }
}

/**
 * 用户侧常驻消息流（spec §13）：接收客服回复 / 审核通过的草稿 / 模式变更。
 * 与 streamChat 不同，这条流跨多条消息长连，直到组件卸载才关闭。
 */
export async function* streamConversationMessages(args: {
  conversationId: number;
}): AsyncGenerator<ChatEvent> {
  const resp = await authedFetch(`/api/v1/conversations/${args.conversationId}/messages-stream`);
  if (!resp.ok || !resp.body) throw new Error(`messages-stream http ${resp.status}`);
  yield* readSseStream(resp);
}

/**
 * 取消生成（spec §3.3）。用户点"停止生成"按钮调。
 */
export async function cancelStream(conversationId: number): Promise<void> {
  await authedFetch(`/api/v1/chat/${conversationId}/stream`, { method: "DELETE" });
}

/**
 * 转人工（MVP-2 §13.7：调 /request-human 端点，置 human_pending + 建工单）。
 */
export async function requestHuman(conversationId: number, reason?: string): Promise<void> {
  await authedFetch(`/api/v1/conversations/${conversationId}/request-human`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason: reason ?? "用户请求人工" }),
  });
}

/**
 * 用户对工单确认（已解决 / 未解决）→ 反向 webhook（spec §7.6）。
 */
export async function sendTicketUserEvent(
  externalId: string,
  event: "user_confirmed_resolved" | "user_rejected_resolved",
  reason?: string,
): Promise<void> {
  await authedFetch(`/api/v1/tickets/${externalId}/user-events`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ event, reason }),
  });
}
