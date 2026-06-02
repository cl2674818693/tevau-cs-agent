import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  cancelStream,
  fetchHistory,
  initConversation,
  reportClientInfo,
  requestHuman,
  streamChat,
  streamConversationMessages,
} from "../api/chat";
import { AuthExpiredError, resolveIdentity, userType } from "../api/identity";
import i18n, { syncLanguageFromBridge } from "../i18n";
import { backoffDelay } from "../lib/backoff";
import {
  loadResumeContext,
  persistConversation,
  touchFallback,
} from "../lib/chatSession";
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
    let attempt = 0;
    const actions: StaffStreamActions = { setMode, setStaffName, setMessages };
    void (async () => {
      while (!stopped) {
        try {
          for await (const ev of streamConversationMessages({ conversationId: convId })) {
            if (stopped) break;
            attempt = 0; // 成功收到事件即视为连上，重置退避
            applyUserStreamEvent(ev, actions);
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

/** 会话初始化（身份解析 + 续接判定 + initConversation + 历史回灌），含 loading/error/重试。 */
function useChatInit(
  setMessages: (fn: (p: Message[]) => Message[]) => void,
  setLimitPct: (n: number) => void,
  setMode: (m: ConversationMode) => void,
  setStaffName: (n: string | undefined) => void,
) {
  const [init, setInit] = useState<ConversationInit | null>(null);
  const [status, setStatus] = useState<InitStatus>("loading");
  const fallbackRef = useRef(false); // 是否走时间窗降级（旧版 APP），决定要不要刷新时间戳
  const loadInit = useCallback(async () => {
    setStatus("loading");
    try {
      await resolveIdentity();
      await syncLanguageFromBridge(); // 外壳语言跟随 APP（C 端）；首屏前完成，避免语言闪烁
      const { sessionId, resume } = await loadResumeContext();
      fallbackRef.current = sessionId === null;
      const info = await initConversation(resume);
      setInit(info);
      setLimitPct(info.limits?.daily_token_used_pct ?? 0);
      setMode(info.mode ?? "ai");
      setStaffName(info.staff_name ?? undefined); // 续接人工会话恢复客服署名
      // 续接成功（后端返回的是同一个会话）才回灌历史；新建则只有 greeting。
      const resumed = resume != null && info.conversation_id === resume;
      const history = resumed && info.history_url ? await fetchHistory(info.history_url) : [];
      setMessages(() => [{ role: "system", content: info.greeting }, ...history]);
      persistConversation(sessionId, info.conversation_id);
      setStatus("ready");
      // 上报客户端环境给 admin 详情页"会话信息"卡用（platform/版本/UA）。
      // 异步触发，失败静默，不阻塞首屏。bridge 不可用时 platform/version 都为空字符串。
      void (async () => {
        try {
          const { bridge } = await import("./useAppBridge");
          const env = await bridge.getEnv();
          await reportClientInfo(info.conversation_id, {
            platform: env.platform ?? undefined,
            app_version: env.version ?? undefined,
            user_agent: typeof navigator !== "undefined" ? navigator.userAgent : undefined,
          });
        } catch {
          /* 静默 */
        }
      })();
    } catch (e) {
      console.error("init failed", e);
      setStatus("error");
    }
  }, [setMessages, setLimitPct, setMode, setStaffName]);
  useEffect(() => {
    void loadInit();
  }, [loadInit]);
  // 降级路径：切后台时刷新时间戳，使时间窗衡量空闲时长而非会话年龄。
  useEffect(() => {
    if (init == null) return;
    const onHide = () => {
      if (fallbackRef.current && document.visibilityState === "hidden")
        touchFallback(init.conversation_id);
    };
    document.addEventListener("visibilitychange", onHide);
    return () => document.removeEventListener("visibilitychange", onHide);
  }, [init]);
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
    async (text: string, attachmentIds?: number[]) => {
      if (!init || rateLimited) return;
      // 幂等键：本次发送固定一个 id，重连/重发复用以避免后端重复处理。
      // 在 setSending 前算好（纯计算），避免中途抛错导致 sending 卡死。
      // HTTP（非安全上下文，如 APP webview 直连内网 IP）不暴露 crypto.randomUUID，故带回退。
      const clientMessageId =
        globalThis.crypto?.randomUUID?.() ??
        `m-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      setSending(true);
      // 本地追加 user 行（沿用既有非乐观以外的本地回显约定），附件用 id 拼看图 URL 渲染
      const atts = (attachmentIds ?? []).map((id) => ({ id, mime: "image/*" }));
      actions.setMessages((prev) => [
        ...prev,
        { role: "user", content: text, attachments: atts },
      ]);
      const controller = new AbortController();
      abortRef.current = controller;
      try {
        for await (const ev of streamChat({
          conversationId: init.conversation_id,
          message: text,
          lastEventId: lastEventIdRef.current,
          signal: controller.signal,
          clientMessageId,
          attachmentIds,
        })) {
          if (ev._eventId) lastEventIdRef.current = ev._eventId;
          await handleStreamEvent(ev, actions);
        }
      } catch (e) {
        if (controller.signal.aborted) {
          /* 用户主动停止，不提示错误 */
        } else if (e instanceof AuthExpiredError) await handleAuthExpired();
        else pushSystem(actions, i18n.t("chat.netError"));
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
  const { init, status, retryInit } = useChatInit(setMessages, setLimitPct, setMode, setStaffName);

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
    // 「已为您请求人工」提示由后端 request_human 事件经常驻流统一驱动（见 chatEvents），
    // 此处不再本地追加，避免与 SSE 回推重复显示两条。
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
