/**
 * 会话续接的本地映射（spec §6.2 resume）。
 *
 * 目标：APP 切后台被系统杀掉后 webview 重载 → 恢复上次对话；用户主动退出页面后重进 → 新对话。
 *
 * 主路径（新版 APP）：bridge.getChatSession() 返回「聊天页路由」级别的 sessionId——
 *   webview 重载时不变、主动退出后重进变新。按 sessionId 存/取 conversation_id 即可精确区分。
 * 降级路径（旧版 APP 无此 handler，sessionId=null）：退化成时间窗——
 *   距上次活跃 < 窗口则续接，否则新对话。无法区分「被杀」与「主动退出后短时间重进」，是已知代价。
 */
import { bridge } from "../hooks/useAppBridge";

const PREFIX = "cs.conv.";
const FALLBACK_KEY = "cs.conv.__fallback__";
const FALLBACK_WINDOW_MS = 30 * 60 * 1000;

function safeGet(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeSet(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* 隐私模式 / localStorage 不可用：放弃续接，降级为每次新对话 */
  }
}

function safeRemove(key: string): void {
  try {
    localStorage.removeItem(key);
  } catch {
    /* ignore */
  }
}

/** 清掉非当前 sessionId 的旧映射，避免 localStorage 无限堆积。 */
function pruneOtherSessions(currentSessionId: string): void {
  const keep = PREFIX + currentSessionId;
  try {
    const toRemove: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k && k.startsWith(PREFIX) && k !== keep && k !== FALLBACK_KEY) toRemove.push(k);
    }
    toRemove.forEach(safeRemove);
  } catch {
    /* ignore */
  }
}

export type ResumeContext = {
  /** 主路径有值；旧版 APP / 浏览器为 null（走时间窗降级）。 */
  sessionId: string | null;
  /** 尝试续接的会话 id；无可续接时 undefined（init 将新建）。 */
  resume: number | undefined;
};

/** 首屏 init 前：决定要不要续接、续接哪条会话。 */
export async function loadResumeContext(): Promise<ResumeContext> {
  let sessionId: string | null = null;
  try {
    sessionId = await bridge.getChatSession();
  } catch {
    sessionId = null;
  }

  if (sessionId) {
    pruneOtherSessions(sessionId);
    const v = safeGet(PREFIX + sessionId);
    const id = v ? Number(v) : NaN;
    return { sessionId, resume: Number.isInteger(id) ? id : undefined };
  }

  // 降级：时间窗
  const raw = safeGet(FALLBACK_KEY);
  if (raw) {
    try {
      const { id, ts } = JSON.parse(raw) as { id?: number; ts?: number };
      if (typeof id === "number" && typeof ts === "number" && Date.now() - ts < FALLBACK_WINDOW_MS)
        return { sessionId: null, resume: id };
    } catch {
      /* 坏数据：忽略 */
    }
  }
  return { sessionId: null, resume: undefined };
}

/** init 之后：把（可能是新建的）conversation_id 落到本地，供下次重载续接。 */
export function persistConversation(sessionId: string | null, convId: number): void {
  if (sessionId) safeSet(PREFIX + sessionId, String(convId));
  else safeSet(FALLBACK_KEY, JSON.stringify({ id: convId, ts: Date.now() }));
}

/** 降级路径专用：刷新时间戳，使时间窗衡量「空闲时长」而非「会话年龄」。 */
export function touchFallback(convId: number): void {
  safeSet(FALLBACK_KEY, JSON.stringify({ id: convId, ts: Date.now() }));
}
