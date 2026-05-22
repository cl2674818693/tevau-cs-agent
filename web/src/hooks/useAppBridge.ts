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
    const t = await call<string>("getToken");
    if (t) return t;
    return urlParams().get("token"); // dev / 旧 APP 兜底
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
