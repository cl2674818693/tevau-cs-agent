import { useCallback, useEffect, useState } from "react";

import { cancelStream, initConversation, streamChat } from "../api/chat";
import type { ConversationInit, Message, ToolCallShown } from "../types";

const BU_ID = "BU00243780"; // MVP-1 写死，MVP-2 接 SSO/JWT

// spec §13.7 + §11 line 551：MVP-1"转人工"按钮发的固定文本
export const HANDOFF_TRIGGER_TEXT = "我想转人工";

export function useChat() {
  const [init, setInit] = useState<ConversationInit | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [sending, setSending] = useState(false);
  const [lastEventId, setLastEventId] = useState<string | undefined>();

  // 首屏调 init（spec §6.2）拿 conversation_id + greeting
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
      const assistant: Message = { role: "assistant", content: "", tool_calls: [] };
      setMessages((prev) => [...prev, assistant]);

      try {
        for await (const ev of streamChat({
          conversationId: init.conversation_id,
          message: text,
          buId: BU_ID,
          lastEventId,
        })) {
          if (ev._eventId) setLastEventId(ev._eventId);
          if (ev.type === "content_block_delta") {
            const delta = ev.delta?.text ?? "";
            setMessages((prev) => {
              const last = prev[prev.length - 1] as Extract<Message, { role: "assistant" }>;
              return [...prev.slice(0, -1), { ...last, content: last.content + delta }];
            });
          } else if (ev.type === "tool_use") {
            const tc: ToolCallShown = { name: ev.name, input: ev.input };
            setMessages((prev) => {
              const last = prev[prev.length - 1] as Extract<Message, { role: "assistant" }>;
              return [
                ...prev.slice(0, -1),
                { ...last, tool_calls: [...(last.tool_calls ?? []), tc] },
              ];
            });
          } else if (ev.type === "tool_result") {
            setMessages((prev) => {
              const last = prev[prev.length - 1] as Extract<Message, { role: "assistant" }>;
              const calls = (last.tool_calls ?? []).slice();
              const i = calls.length - 1;
              if (i >= 0) calls[i] = { ...calls[i], ok: !ev.is_error };
              return [...prev.slice(0, -1), { ...last, tool_calls: calls }];
            });
          } else if (ev.type === "error") {
            console.warn("sse error", ev);
          }
        }
      } finally {
        setSending(false);
      }
    },
    [init, lastEventId],
  );

  // spec §13.7 + §11 line 551："没解决？转人工"按钮 onClick
  const requestHandoff = useCallback(() => send(HANDOFF_TRIGGER_TEXT), [send]);

  // spec §3.3 取消生成
  const stop = useCallback(() => {
    if (init) cancelStream(init.conversation_id, BU_ID);
  }, [init]);

  return { messages, sending, send, requestHandoff, stop, init };
}
