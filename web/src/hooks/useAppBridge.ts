/**
 * C 端 APP JS Bridge（spec §4.1.1）。Flutter + flutter_inappwebview 注入
 * window.flutter_inappwebview.callHandler(name, ...args)。
 * 冷启动 H5 可能早于 bridge 注入，故任何调用前 await whenReady()（poll 50ms / timeout 5s）。
 * 不可用时（旧 APP / 浏览器调试）降级到 URL query 读 token/lange/env。
 */

interface BridgeResponse<T> {
  code: number;
  data: T;
  message: string;
}

export interface EnvInfo {
  language?: string;
  platform?: string;
  version?: string;
  env?: string;
}

declare global {
  interface Window {
    flutter_inappwebview?: {
      callHandler: (name: string, ...args: unknown[]) => Promise<BridgeResponse<unknown>>;
    };
  }
}

const READY_POLL_MS = 50;
const READY_TIMEOUT_MS = 5000;

async function whenReady(): Promise<boolean> {
  const deadline = Date.now() + READY_TIMEOUT_MS;
  while (Date.now() < deadline) {
    if (typeof window !== "undefined" && window.flutter_inappwebview?.callHandler) return true;
    await new Promise((r) => setTimeout(r, READY_POLL_MS));
  }
  return false;
}

async function call<T>(name: string, ...args: unknown[]): Promise<T | null> {
  const handler = window.flutter_inappwebview?.callHandler;
  if (!handler) return null;
  try {
    const resp = (await handler(name, ...args)) as BridgeResponse<T>;
    return resp && resp.code === 0 ? resp.data : null;
  } catch {
    return null;
  }
}

function urlParams(): URLSearchParams {
  return new URLSearchParams(typeof location !== "undefined" ? location.search : "");
}

export const bridge = {
  whenReady,
  async getToken(): Promise<string | null> {
    // native getToken 的 data 包了一层 {token}（js_bridge.dart _handleGetToken），
    // 这里取出裸字符串；兼容旧实现直接返回字符串的情况。
    const d = await call<{ token?: string } | string | null>("getToken");
    const t = typeof d === "string" ? d : (d?.token ?? null);
    if (t) return t;
    return urlParams().get("token"); // dev / 旧 APP 兜底
  },
  /**
   * 本次聊天页的会话标识（APP 端 getChatSession，见 js_bridge.dart）。
   * 语义：webview 被系统回收后重载返回同一个 id；用户主动退出页面后重进是新 id。
   * H5 据此区分「切后台被杀→恢复对话」与「主动退出→新对话」。
   * 旧版 APP 无此 handler 时返回 null，调用方降级到时间窗。
   */
  async getChatSession(): Promise<string | null> {
    const d = await call<{ sessionId?: string | null } | string | null>("getChatSession");
    if (typeof d === "string") return d || null;
    return d?.sessionId ?? null;
  },
  async getEnv(): Promise<EnvInfo> {
    const env = await call<EnvInfo>("getEnv");
    if (env) return env;
    const p = urlParams();
    return { language: p.get("lange") ?? undefined, env: p.get("env") ?? undefined };
  },
  async logout(): Promise<void> {
    await call("logout");
  },
  async navigate(target: string): Promise<void> {
    await call("navigate", target);
  },
};
