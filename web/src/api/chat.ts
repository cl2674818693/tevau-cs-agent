import type { ChatEvent, ConversationInit } from "../types";

/**
 * 会话初始化（spec §6.2）。首屏调一次，拿 user_type / display_name / greeting / limits。
 */
export async function initConversation(buId: string): Promise<ConversationInit> {
  const resp = await fetch("/api/v1/conversations", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-BU-ID": buId },
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
  buId: string;
  lastEventId?: string;
}): AsyncGenerator<ChatEvent> {
  const url = `/api/v1/chat?conversation_id=${args.conversationId}&message=${encodeURIComponent(
    args.message,
  )}`;
  const headers: Record<string, string> = { "X-BU-ID": args.buId };
  if (args.lastEventId) headers["Last-Event-ID"] = args.lastEventId;
  const resp = await fetch(url, { headers });
  if (!resp.ok || !resp.body) throw new Error(`chat http ${resp.status}`);

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
 * 取消生成（spec §3.3）。用户点"停止生成"按钮调。
 */
export async function cancelStream(conversationId: number, buId: string): Promise<void> {
  await fetch(`/api/v1/chat/${conversationId}/stream`, {
    method: "DELETE",
    headers: { "X-BU-ID": buId },
  });
}
