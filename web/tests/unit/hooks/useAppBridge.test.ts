// useAppBridge：JS Bridge 契约（getToken/getChatSession/getEnv/navigate/logout）+ URL 兜底。
// 注意 spec：getToken 的 data 是 { token } 包装；bridge 不可用时回退 URL ?token。
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { bridge } from "@/hooks/useAppBridge";

type Handler = (name: string, ...args: unknown[]) => Promise<{ code: number; data: unknown; message?: string }>;

function installBridge(handler: Handler) {
  Object.defineProperty(window, "flutter_inappwebview", {
    configurable: true,
    writable: true,
    value: { callHandler: handler },
  });
}

function uninstallBridge() {
  Object.defineProperty(window, "flutter_inappwebview", {
    configurable: true,
    writable: true,
    value: undefined,
  });
}

describe("useAppBridge", () => {
  beforeEach(() => {
    uninstallBridge();
    window.history.replaceState({}, "", "/");
  });
  afterEach(() => {
    uninstallBridge();
    window.history.replaceState({}, "", "/");
  });

  describe("getToken", () => {
    it("bridge 返回 {token} 形式 → 取 token 字段", async () => {
      installBridge(vi.fn(async (n) => (n === "getToken" ? { code: 0, data: { token: "tk" } } : { code: 0, data: null })));
      expect(await bridge.getToken()).toBe("tk");
    });

    it("bridge 返回裸字符串（旧实现） → 直接用", async () => {
      installBridge(vi.fn(async () => ({ code: 0, data: "raw-tk" })));
      expect(await bridge.getToken()).toBe("raw-tk");
    });

    it("bridge 不可用 → 回退 URL ?token", async () => {
      window.history.replaceState({}, "", "/?token=urltk");
      expect(await bridge.getToken()).toBe("urltk");
    });

    it("bridge 与 URL 都没有 → null", async () => {
      expect(await bridge.getToken()).toBeNull();
    });

    it("bridge code != 0 → 视为失败，回退 URL", async () => {
      installBridge(vi.fn(async () => ({ code: 1, data: null, message: "fail" })));
      window.history.replaceState({}, "", "/?token=urltk");
      expect(await bridge.getToken()).toBe("urltk");
    });

    it("handler 抛错 → 回退 URL", async () => {
      installBridge(vi.fn(async () => {
        throw new Error("native crashed");
      }));
      window.history.replaceState({}, "", "/?token=urltk");
      expect(await bridge.getToken()).toBe("urltk");
    });
  });

  describe("getChatSession", () => {
    it("bridge 返回 {sessionId} → 取出", async () => {
      installBridge(vi.fn(async () => ({ code: 0, data: { sessionId: "s1" } })));
      expect(await bridge.getChatSession()).toBe("s1");
    });

    it("bridge 返回裸字符串 → 直接用", async () => {
      installBridge(vi.fn(async () => ({ code: 0, data: "raw-s" })));
      expect(await bridge.getChatSession()).toBe("raw-s");
    });

    it("bridge 返回空字符串归一为 null", async () => {
      installBridge(vi.fn(async () => ({ code: 0, data: "" })));
      expect(await bridge.getChatSession()).toBeNull();
    });

    it("旧版 APP 无 handler 时 null", async () => {
      expect(await bridge.getChatSession()).toBeNull();
    });
  });

  describe("getEnv", () => {
    it("bridge 返回完整 env", async () => {
      installBridge(vi.fn(async () => ({ code: 0, data: { language: "en", platform: "ios" } })));
      expect(await bridge.getEnv()).toEqual({ language: "en", platform: "ios" });
    });

    it("无 bridge → URL ?lange/?env 兜底", async () => {
      window.history.replaceState({}, "", "/?lange=en&env=dev");
      expect(await bridge.getEnv()).toMatchObject({ language: "en", env: "dev" });
    });

    it("无 bridge 也无 URL 时返回空对象（不抛）", async () => {
      const env = await bridge.getEnv();
      expect(env.language).toBeUndefined();
      expect(env.env).toBeUndefined();
    });
  });

  describe("navigate / logout", () => {
    it("navigate 转发 target", async () => {
      const spy = vi.fn(async () => ({ code: 0, data: null }));
      installBridge(spy);
      await bridge.navigate("/foo");
      expect(spy).toHaveBeenCalledWith("navigate", "/foo");
    });

    it("logout 调用 native logout", async () => {
      const spy = vi.fn(async () => ({ code: 0, data: null }));
      installBridge(spy);
      await bridge.logout();
      expect(spy).toHaveBeenCalledWith("logout");
    });

    it("bridge 不可用时 navigate/logout 静默 no-op", async () => {
      await expect(bridge.navigate("/x")).resolves.toBeUndefined();
      await expect(bridge.logout()).resolves.toBeUndefined();
    });
  });

  describe("whenReady", () => {
    it("bridge 立即可用 → true", async () => {
      installBridge(vi.fn(async () => ({ code: 0, data: null })));
      expect(await bridge.whenReady()).toBe(true);
    });

    // 注：超时分支会真等 5s，跑测试不友好；这里只验"立即可用"分支足够。
  });
});
