import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  cancelStream,
  initConversation,
  requestHuman,
  streamChat,
  streamConversationMessages,
} from "../api/chat";
import { AuthExpiredError, resolveIdentity, userType } from "../api/identity";
import type { ConversationInit, ConversationMode, Message } from "../types";
import {
  type ChatActions,
  type StaffStreamActions,
  applyUserStreamEvent,
  handleStreamEvent,
  pushSystem,
} from "./chatEvents";

type InitStatus = "loading" | "ready" | "error";
type Connection = "online" | "offline" | "reconnecting";

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
    const actions: StaffStreamActions = { setMode, setStaffName, setMessages };
    void (async () => {
      while (!stopped) {
        try {
          for await (const ev of streamConversationMessages({ conversationId: convId })) {
            if (stopped) break;
            applyUserStreamEvent(ev, actions);
          }
        } catch {
          /* 流断开，退避后重连 */
        }
        if (stopped) break;
        await new Promise((r) => setTimeout(r, 2000));
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

/** 发送 + 停止：封装 AbortController（停止时立刻复位 sending 并中断本地 SSE 读取）。 */
function useChatSend(
  init: ConversationInit | null,
  rateLimited: boolean,
  handleAuthExpired: () => Promise<void>,
  actions: ChatActions,
) {
  const [sending, setSending] = useState(false);
  const lastEventIdRef = useRef<string | undefined>(undefined);
  const abortRef = useRef<AbortController | null>(null);

  const send = useCallback(
    async (text: string) => {
      if (!init || rateLimited) return;
      setSending(true);
      actions.setMessages((prev) => [...prev, { role: "user", content: text }]);
      const controller = new AbortController();
      abortRef.current = controller;
      try {
        for await (const ev of streamChat({
          conversationId: init.conversation_id,
          message: text,
          lastEventId: lastEventIdRef.current,
          signal: controller.signal,
        })) {
          if (ev._eventId) lastEventIdRef.current = ev._eventId;
          await handleStreamEvent(ev, actions);
        }
      } catch (e) {
        if (controller.signal.aborted) {
          /* 用户主动停止，不提示错误 */
        } else if (e instanceof AuthExpiredError) await handleAuthExpired();
        else pushSystem(actions, "网络中断，请检查连接后重试。");
      } finally {
        if (abortRef.current === controller) abortRef.current = null;
        setSending(false);
      }
    },
    [init, rateLimited, handleAuthExpired, actions],
  );

  const stop = useCallback(() => {
    // 同时中断本地 SSE 读取（立刻复位 sending/输入框）和通知后端关流
    abortRef.current?.abort();
    setSending(false);
    if (init) void cancelStream(init.conversation_id);
  }, [init]);

  return { sending, send, stop };
}

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [mode, setMode] = useState<ConversationMode>("ai");
  const [staffName, setStaffName] = useState<string | undefined>();
  const [connection, setConnection] = useOnlineStatus();
  const [limitPct, setLimitPct] = useState(0);
  const [rateLimited, setRateLimited] = useState(false);
  const { init, status, retryInit } = useChatInit(setMessages, setLimitPct);

  useStaffMessageStream(init?.conversation_id, setMode, setStaffName, setMessages);

  const handleAuthExpired = useAuthExpiredHandler(setConnection);
  const actions: ChatActions = useMemo(
    () => ({ setMode, setMessages, setLimitPct, setRateLimited, onAuthExpired: handleAuthExpired }),
    [handleAuthExpired],
  );
  const { sending, send, stop } = useChatSend(init, rateLimited, handleAuthExpired, actions);

  const requestHandoff = useCallback(async () => {
    if (!init) return;
    if (init.user_type === "g") {
      setMessages((prev) => [
        ...prev,
        { role: "system", content: "转接人工客服需要先在 APP 内登录。" },
      ]);
      return;
    }
    await requestHuman(init.conversation_id);
    setMode("human_pending");
    setMessages((prev) => [...prev, { role: "system", content: "已为您请求人工，请稍候…" }]);
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
