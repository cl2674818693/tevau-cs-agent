import type { ChatEvent, ConversationMode, Message } from "../types";

type AssistantMsg = Extract<Message, { role: "assistant" }>;

function _patchLastAssistant(prev: Message[], patch: (a: AssistantMsg) => AssistantMsg): Message[] {
  const last = prev[prev.length - 1] as AssistantMsg;
  return [...prev.slice(0, -1), patch(last)];
}

/** 把一个 SSE 事件应用到消息列表（纯函数）。 */
export function applyEvent(prev: Message[], ev: ChatEvent): Message[] {
  if (ev.type === "message_start")
    return [...prev, { role: "assistant", content: "", tool_calls: [] }];
  if (ev.type === "human_message")
    return [
      ...prev,
      {
        role: "human_agent",
        content: ev.content,
        display_name: ev.display_name,
        attachments: ev.attachments,
      },
    ];
  if (ev.type === "assistant_message")
    return [...prev, { role: "assistant", content: ev.content, attachments: ev.attachments }];
  if (ev.type === "content_block_delta") {
    const text = ev.delta?.text ?? "";
    return _patchLastAssistant(prev, (a) => ({ ...a, content: a.content + text }));
  }
  if (ev.type === "tool_use") {
    const tc = { tool_use_id: ev.tool_use_id, name: ev.name, input: ev.input };
    return _patchLastAssistant(prev, (a) => ({ ...a, tool_calls: [...(a.tool_calls ?? []), tc] }));
  }
  if (ev.type === "tool_result") {
    return _patchLastAssistant(prev, (a) => {
      const calls = (a.tool_calls ?? []).slice();
      // 按 tool_use_id 精确配对（并发多工具时不会错配）；缺 id 时回退到最后一个
      let i = ev.tool_use_id ? calls.findIndex((c) => c.tool_use_id === ev.tool_use_id) : -1;
      if (i === -1) i = calls.length - 1;
      if (i >= 0) calls[i] = { ...calls[i], ok: !ev.is_error };
      return { ...a, tool_calls: calls };
    });
  }
  return prev;
}

export type ChatActions = {
  setMode: (m: ConversationMode) => void;
  setMessages: (fn: (p: Message[]) => Message[]) => void;
  setLimitPct: (n: number) => void;
  setRateLimited: (b: boolean) => void;
  onAuthExpired: () => Promise<void>;
};

export function pushSystem(a: ChatActions, content: string) {
  a.setMessages((p) => [...p, { role: "system", content }]);
}

/** 移除尾部「空 assistant 占位气泡」：message_start 建了它但回合出错/中断后再无内容填入，
 *  否则会永久卡在「思考中…」。仅当最后一条是无文本无工具调用的 assistant 时剥离。 */
function dropTrailingEmptyAssistant(prev: Message[]): Message[] {
  const last = prev[prev.length - 1];
  if (last?.role === "assistant" && !last.content && !(last.tool_calls?.length)) {
    return prev.slice(0, -1);
  }
  return prev;
}

/** F-P1-5: RATE_LIMITED 锁定输入框的自动解锁时长（与后端 chat_rate_limit_per_min 窗口对齐）。 */
export const RATE_LIMITED_AUTO_UNLOCK_MS = 60_000;

async function handleErrorEvent(
  ev: Extract<ChatEvent, { type: "error" }>,
  a: ChatActions,
): Promise<void> {
  // 回合失败：先剥掉 message_start 留下的空占位气泡，避免「思考中…」与错误提示并存
  a.setMessages(dropTrailingEmptyAssistant);
  if (ev.code === "RATE_LIMITED") {
    a.setRateLimited(true);
    pushSystem(a, ev.message || "请求过于频繁，请稍后再试。");
    // F-P1-5: 60s 后自动解锁，避免用户必须手动刷新；时间窗与后端兜底限流对齐
    setTimeout(() => a.setRateLimited(false), RATE_LIMITED_AUTO_UNLOCK_MS);
  } else if (ev.code === "SYSTEM_BUSY") {
    // 后端 Semaphore 满载（区别于 RATE_LIMITED 用户级限流）：不锁死输入，让用户手动重试
    pushSystem(a, ev.message || "系统繁忙，请稍后再试。");
  } else if (ev.code === "MODEL_OVERLOADED") {
    // F-P0-5: 区分于 SYSTEM_BUSY（本服务过载）—— 模型方过载，独立提示让用户知道是上游。
    pushSystem(a, ev.message || "模型暂时超载，请稍后重试。");
  } else if (ev.code === "AUTH_EXPIRED") {
    await a.onAuthExpired();
  } else {
    // F-P0-5: 兜底文案显式不带技术细节（堆栈/路径/SQL）
    pushSystem(a, ev.message || "服务出错了，请稍后重试。");
  }
}

/** 处理一个主链路 SSE 事件（拆出以降低 send 复杂度）。 */
export async function handleStreamEvent(ev: ChatEvent, a: ChatActions): Promise<void> {
  if (ev.type === "mode_change") {
    // 仅更新 mode state。不在这里 push "已为您转接人工客服"——
    // AI 在 create_ticket 后那条回复里已经说过这句（reply_style 硬性要求），
    // 前端再 push 一遍会重复；且后端 chat.py 在 mode 已为 human_pending 时不再重推 mode_change，
    // 切换由 _ensure_human_pending 经常驻流广播一次足够。
    a.setMode(ev.to as ConversationMode);
  } else if (ev.type === "warning") {
    if (typeof ev.pct === "number") a.setLimitPct(ev.pct);
    if (ev.text) pushSystem(a, ev.text);
  } else if (ev.type === "error") {
    await handleErrorEvent(ev, a);
  } else {
    a.setMessages((p) => applyEvent(p, ev));
  }
}

export type StaffStreamActions = {
  setMode: (m: ConversationMode) => void;
  setStaffName: (n: string | undefined) => void;
  setMessages: (fn: (p: Message[]) => Message[]) => void;
};

/** 把一条用户侧常驻流事件应用到状态（客服→用户方向）。 */
export function applyUserStreamEvent(ev: ChatEvent, a: StaffStreamActions): void {
  if (ev.type === "mode_change") {
    a.setMode(ev.to as ConversationMode);
    // 客服接管后给用户一条明确提示，否则消息流停留在「请求人工，请稍候」，感知不到已接入
    if (ev.to === "human_takeover")
      a.setMessages((p) => [...p, { role: "system", content: "客服已接入，将为您服务。" }]);
  } else if (ev.type === "human_message") {
    a.setStaffName(ev.display_name ?? ev.sender_staff_id);
    a.setMessages((p) => applyEvent(p, ev));
  } else if (ev.type === "assistant_message") a.setMessages((p) => applyEvent(p, ev));
  else if (ev.type === "transferred")
    a.setMessages((p) => [...p, { role: "system", content: "已为您转接给其他客服，请稍候…" }]);
  else if (ev.type === "request_human") {
    a.setMode("human_pending");
    a.setMessages((p) => [...p, { role: "system", content: "已为您请求人工，请稍候…" }]);
  }
}
