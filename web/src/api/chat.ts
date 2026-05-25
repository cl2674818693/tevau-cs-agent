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
  signal?: AbortSignal;
}): AsyncGenerator<ChatEvent> {
  const url = `/api/v1/chat?conversation_id=${args.conversationId}&message=${encodeURIComponent(
    args.message,
  )}`;
  const headers: Record<string, string> = {};
  if (args.lastEventId) headers["Last-Event-ID"] = args.lastEventId;
  const resp = await authedFetch(url, { headers, signal: args.signal });
  if (!resp.ok || !resp.body) throw new Error(`chat http ${resp.status}`);
  yield* readSseStream(resp);
}

/** 读取一个 SSE 响应体，逐 frame 解析成 ChatEvent。 */
async function* readSseStream(resp: Response): AsyncGenerator<ChatEvent> {
  if (!resp.body) return;
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  // SSE 帧分隔符：sse-starlette 默认用 \r\n\r\n，规范也允许 \r\r / \n\n。
  // 只认 \n\n 会导致 \r\n\r\n 永远切不出帧（事件全丢，UI 不渲染）。
  const FRAME_SEP = /\r\n\r\n|\r\r|\n\n/;
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let m: RegExpExecArray | null;
    while ((m = FRAME_SEP.exec(buffer)) !== null) {
      const frame = buffer.slice(0, m.index);
      buffer = buffer.slice(m.index + m[0].length);
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
 * 工单状态 SSE（spec §7.2）：订阅该会话的工单生命周期事件。
 * 必须走 authedFetch 而非原生 EventSource —— EventSource 无法携带 Bearer / X-Guest-ID 头，
 * 会导致 C 端/游客被降级成 guest:anon 而 403（B 端因 cookie 自动携带才侥幸可用）。
 */
export async function* streamTicketEvents(args: {
  conversationId: number;
}): AsyncGenerator<ChatEvent> {
  const resp = await authedFetch(
    `/api/v1/conversations/${args.conversationId}/ticket-events-stream`,
  );
  if (!resp.ok || !resp.body) throw new Error(`ticket-events-stream http ${resp.status}`);
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
