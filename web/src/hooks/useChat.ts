import { useCallback, useEffect, useRef, useState } from "react";

import {
  cancelStream,
  initConversation,
  requestHuman,
  streamChat,
  streamConversationMessages,
} from "../api/chat";
import { AuthExpiredError, resolveIdentity, userType } from "../api/identity";
import i18n from "../i18n";
import { backoffDelay } from "../lib/backoff";
import type { ChatEvent, ConversationInit, ConversationMode, Message } from "../types";

type AssistantMsg = Extract<Message, { role: "assistant" }>;
type InitStatus = "loading" | "ready" | "error";
type Connection = "online" | "offline" | "reconnecting";

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
  if (ev.type === "assistant_message") return [...prev, { role: "assistant", content: ev.content }];
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

type ChatActions = {
  setMode: (m: ConversationMode) => void;
  setMessages: (fn: (p: Message[]) => Message[]) => void;
  setLimitPct: (n: number) => void;
  setRateLimited: (b: boolean) => void;
  onAuthExpired: () => Promise<void>;
};

function pushSystem(a: ChatActions, content: string) {
  a.setMessages((p) => [...p, { role: "system", content }]);
}

async function handleErrorEvent(
  ev: Extract<ChatEvent, { type: "error" }>,
  a: ChatActions,
): Promise<void> {
  if (ev.code === "RATE_LIMITED") {
    a.setRateLimited(true);
    pushSystem(a, ev.message || "请求过于频繁，请稍后再试。");
  } else if (ev.code === "AUTH_EXPIRED") {
    await a.onAuthExpired();
  } else {
    pushSystem(a, ev.message || "出错了，请重试。");
  }
}

/** 处理一个主链路 SSE 事件（拆出以降低 send 复杂度）。 */
async function handleStreamEvent(ev: ChatEvent, a: ChatActions): Promise<void> {
  if (ev.type === "mode_change") {
    a.setMode(ev.to as ConversationMode);
    if (ev.to !== "ai") pushSystem(a, "已为您转接人工客服，请稍候…");
  } else if (ev.type === "warning") {
    if (typeof ev.pct === "number") a.setLimitPct(ev.pct);
    if (ev.text) pushSystem(a, ev.text);
  } else if (ev.type === "error") {
    await handleErrorEvent(ev, a);
  } else {
    a.setMessages((p) => applyEvent(p, ev));
  }
}

/** 在线/离线监听（spec §13.6 offline）。 */
function useOnlineStatus(): [Connection, (c: Connection) => void] {
  const [connection, setConnection] = useState<Connection>("online");
  useEffect(() => {
    const on = () => setConnection("online");
    const off = () => setConnection("offline");
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    if (typeof navigator !== "undefined" && navigator.onLine === false) setConnection("offline");
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);
  return [connection, setConnection];
}

/** 常驻订阅客服→用户方向消息，断线退避自动重连（spec §13 / §3.3）。setter 取自 useState，稳定。 */
function useStaffMessageStream(
  convId: number | undefined,
  setMode: (m: ConversationMode) => void,
  setStaffName: (n: string | undefined) => void,
  setMessages: (fn: (p: Message[]) => Message[]) => void,
): void {
  useEffect(() => {
    if (convId == null) return;
    let stopped = false;
    let attempt = 0;
    void (async () => {
      while (!stopped) {
        try {
          for await (const ev of streamConversationMessages({ conversationId: convId })) {
            if (stopped) break;
            attempt = 0; // 成功收到事件即视为连上，重置退避
            if (ev.type === "mode_change") setMode(ev.to as ConversationMode);
            else if (ev.type === "human_message") {
              setStaffName(ev.display_name);
              setMessages((p) => applyEvent(p, ev));
            } else if (ev.type === "assistant_message") setMessages((p) => applyEvent(p, ev));
          }
        } catch {
          /* 流断开，指数退避后重连 */
        }
        if (stopped) break;
        // 指数退避 + 抖动：避免大量客户端断线后同时重连压垮服务端
        await new Promise((r) => setTimeout(r, backoffDelay(attempt++)));
      }
    })();
    return () => {
      stopped = true;
    };
  }, [convId, setMode, setStaffName, setMessages]);
}

/** 401 处理：C 端置 reconnecting（下次请求 bridge 续 token）；B 端跳登录页。 */
function useAuthExpiredHandler(setConnection: (c: Connection) => void): () => Promise<void> {
  return useCallback(async () => {
    if (userType() === "b") {
      window.location.href = "/bu/login";
      return;
    }
    setConnection("reconnecting");
  }, [setConnection]);
}

/** 会话初始化（身份解析 + initConversation），含 loading/error/重试。 */
function useChatInit(
  setMessages: (fn: (p: Message[]) => Message[]) => void,
  setLimitPct: (n: number) => void,
) {
  const [init, setInit] = useState<ConversationInit | null>(null);
  const [status, setStatus] = useState<InitStatus>("loading");
  const loadInit = useCallback(async () => {
    setStatus("loading");
    try {
      await resolveIdentity();
      const info = await initConversation();
      setInit(info);
      setLimitPct(info.limits?.daily_token_used_pct ?? 0);
      setMessages(() => [{ role: "system", content: info.greeting }]);
      setStatus("ready");
    } catch (e) {
      console.error("init failed", e);
      setStatus("error");
    }
  }, [setMessages, setLimitPct]);
  useEffect(() => {
    void loadInit();
  }, [loadInit]);
  return { init, status, retryInit: loadInit };
}

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [sending, setSending] = useState(false);
  const [mode, setMode] = useState<ConversationMode>("ai");
  const [staffName, setStaffName] = useState<string | undefined>();
  const [connection, setConnection] = useOnlineStatus();
  const [limitPct, setLimitPct] = useState(0);
  const [rateLimited, setRateLimited] = useState(false);
  const lastEventIdRef = useRef<string | undefined>(undefined);
  const { init, status, retryInit } = useChatInit(setMessages, setLimitPct);

  useStaffMessageStream(init?.conversation_id, setMode, setStaffName, setMessages);

  const handleAuthExpired = useAuthExpiredHandler(setConnection);

  const send = useCallback(
    async (text: string) => {
      if (!init || rateLimited) return;
      setSending(true);
      setMessages((prev) => [...prev, { role: "user", content: text }]);
      const actions: ChatActions = {
        setMode,
        setMessages,
        setLimitPct,
        setRateLimited,
        onAuthExpired: handleAuthExpired,
      };
      // 幂等键：本次发送固定一个 id，重连/重发复用以避免后端重复处理
      const clientMessageId = crypto.randomUUID();
      try {
        for await (const ev of streamChat({
          conversationId: init.conversation_id,
          message: text,
          lastEventId: lastEventIdRef.current,
          clientMessageId,
        })) {
          if (ev._eventId) lastEventIdRef.current = ev._eventId;
          await handleStreamEvent(ev, actions);
        }
      } catch (e) {
        if (e instanceof AuthExpiredError) await handleAuthExpired();
        else pushSystem(actions, i18n.t("chat.netError"));
      } finally {
        setSending(false);
      }
    },
    [init, rateLimited, handleAuthExpired],
  );

  const requestHandoff = useCallback(async () => {
    if (!init) return;
    await requestHuman(init.conversation_id);
    setMode("human_pending");
    setMessages((prev) => [...prev, { role: "system", content: "已为您请求人工，请稍候…" }]);
  }, [init]);

  const stop = useCallback(() => {
    if (init) void cancelStream(init.conversation_id);
  }, [init]);

  return {
    messages,
    sending,
    mode,
    staffName,
    status,
    connection,
    limitPct,
    rateLimited,
    send,
    requestHandoff,
    stop,
    init,
    retryInit,
  };
}
