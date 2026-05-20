import { useCallback, useEffect, useState } from "react";

import { cancelStream, initConversation, requestHuman, streamChat } from "../api/chat";
import type { ChatEvent, ConversationInit, ConversationMode, Message } from "../types";

const BU_ID = "BU00243780"; // MVP-1 写死，MVP-2 接 SSO/JWT

type AssistantMsg = Extract<Message, { role: "assistant" }>;

function _patchLastAssistant(prev: Message[], patch: (a: AssistantMsg) => AssistantMsg): Message[] {
  const last = prev[prev.length - 1] as AssistantMsg;
  return [...prev.slice(0, -1), patch(last)];
}

/** 把一个 SSE 事件应用到消息列表（纯函数，降低 useChat 复杂度）。 */
function applyEvent(prev: Message[], ev: ChatEvent): Message[] {
  if (ev.type === "message_start")
    return [...prev, { role: "assistant", content: "", tool_calls: [] }];
  if (ev.type === "human_message")
    return [...prev, { role: "human_agent", content: ev.content, display_name: ev.display_name }];
  if (ev.type === "content_block_delta") {
    const text = ev.delta?.text ?? "";
    return _patchLastAssistant(prev, (a) => ({ ...a, content: a.content + text }));
  }
  if (ev.type === "tool_use") {
    const tc = { name: ev.name, input: ev.input };
    return _patchLastAssistant(prev, (a) => ({ ...a, tool_calls: [...(a.tool_calls ?? []), tc] }));
  }
  if (ev.type === "tool_result") {
    return _patchLastAssistant(prev, (a) => {
      const calls = (a.tool_calls ?? []).slice();
      if (calls.length) calls[calls.length - 1] = { ...calls[calls.length - 1], ok: !ev.is_error };
      return { ...a, tool_calls: calls };
    });
  }
  return prev;
}

export function useChat() {
  const [init, setInit] = useState<ConversationInit | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [sending, setSending] = useState(false);
  const [mode, setMode] = useState<ConversationMode>("ai");
  const [lastEventId, setLastEventId] = useState<string | undefined>();

  useEffect(() => {
    initConversation(BU_ID)
      .then((info) => {
        setInit(info);
        setMessages([{ role: "system", content: info.greeting }]);
      })
      .catch((e) => console.error("init failed", e));
  }, []);

  const send = useCallback(
    async (text: string) => {
      if (!init) return;
      setSending(true);
      setMessages((prev) => [...prev, { role: "user", content: text }]);
      try {
        for await (const ev of streamChat({
          conversationId: init.conversation_id,
          message: text,
          buId: BU_ID,
          lastEventId,
        })) {
          if (ev._eventId) setLastEventId(ev._eventId);
          if (ev.type === "mode_change") {
            setMode(ev.to as ConversationMode);
            if (ev.to !== "ai") {
              setMessages((p) => [
                ...p,
                { role: "system", content: "已为您转接人工客服，请稍候…" },
              ]);
            }
          } else if (ev.type === "error") {
            console.warn("sse error", ev);
          } else {
            setMessages((p) => applyEvent(p, ev));
          }
        }
      } finally {
        setSending(false);
      }
    },
    [init, lastEventId],
  );

  // MVP-2 §13.7：调 /request-human 端点（置 human_pending + 建工单）
  const requestHandoff = useCallback(async () => {
    if (!init) return;
    await requestHuman(init.conversation_id, BU_ID);
    setMode("human_pending");
    setMessages((prev) => [...prev, { role: "system", content: "已为您请求人工，请稍候…" }]);
  }, [init]);

  const stop = useCallback(() => {
    if (init) cancelStream(init.conversation_id, BU_ID);
  }, [init]);

  return { messages, sending, mode, send, requestHandoff, stop, init };
}
