// chatSession 维护"会话续接"的本地映射：
// 1) 新版 APP 有 sessionId → 按 sessionId 索引 conversation_id
// 2) 老版 APP 无 sessionId → 回退到 30 分钟时间窗
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { loadResumeContext, persistConversation, touchFallback } from "@/lib/chatSession";

// 关键：用模块 mock 拦截 useAppBridge.bridge.getChatSession
const getChatSessionMock = vi.fn<() => Promise<string | null>>();

vi.mock("@/hooks/useAppBridge", () => ({
  bridge: {
    getChatSession: () => getChatSessionMock(),
  },
}));

function clearLs() {
  // 沙箱 localStorage 缺 .clear()；按 key 删。
  const keys: string[] = [];
  for (let i = 0; i < localStorage.length; i++) {
    const k = localStorage.key(i);
    if (k) keys.push(k);
  }
  keys.forEach((k) => localStorage.removeItem(k));
}

describe("chatSession 续接上下文", () => {
  beforeEach(() => {
    clearLs();
    getChatSessionMock.mockReset();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  describe("主路径：bridge.getChatSession 返回 sessionId", () => {
    it("无任何历史记录时 resume=undefined", async () => {
      getChatSessionMock.mockResolvedValue("sess-1");
      const r = await loadResumeContext();
      expect(r.sessionId).toBe("sess-1");
      expect(r.resume).toBeUndefined();
    });

    it("命中映射时返回 conversation_id", async () => {
      getChatSessionMock.mockResolvedValue("sess-1");
      localStorage.setItem("cs.conv.sess-1", "42");
      const r = await loadResumeContext();
      expect(r.resume).toBe(42);
    });

    it("非数字值视为 undefined", async () => {
      getChatSessionMock.mockResolvedValue("sess-1");
      localStorage.setItem("cs.conv.sess-1", "not-a-number");
      const r = await loadResumeContext();
      expect(r.resume).toBeUndefined();
    });

    it("非当前 sessionId 的旧映射被清理（fallback 保留）", async () => {
      getChatSessionMock.mockResolvedValue("current");
      localStorage.setItem("cs.conv.current", "1");
      localStorage.setItem("cs.conv.old1", "2");
      localStorage.setItem("cs.conv.old2", "3");
      localStorage.setItem(
        "cs.conv.__fallback__",
        JSON.stringify({ id: 99, ts: Date.now() }),
      );
      await loadResumeContext();
      expect(localStorage.getItem("cs.conv.current")).toBe("1");
      expect(localStorage.getItem("cs.conv.old1")).toBeNull();
      expect(localStorage.getItem("cs.conv.old2")).toBeNull();
      expect(localStorage.getItem("cs.conv.__fallback__")).not.toBeNull();
    });
  });

  describe("降级路径：bridge 返回 null（旧版 APP）", () => {
    it("无 fallback 记录时 resume=undefined", async () => {
      getChatSessionMock.mockResolvedValue(null);
      const r = await loadResumeContext();
      expect(r.sessionId).toBeNull();
      expect(r.resume).toBeUndefined();
    });

    it("fallback 在窗口内时续接", async () => {
      getChatSessionMock.mockResolvedValue(null);
      localStorage.setItem(
        "cs.conv.__fallback__",
        JSON.stringify({ id: 7, ts: Date.now() - 60_000 }),
      );
      const r = await loadResumeContext();
      expect(r.resume).toBe(7);
    });

    it("fallback 超过窗口（30min）时不续接", async () => {
      getChatSessionMock.mockResolvedValue(null);
      localStorage.setItem(
        "cs.conv.__fallback__",
        JSON.stringify({ id: 7, ts: Date.now() - 31 * 60_000 }),
      );
      const r = await loadResumeContext();
      expect(r.resume).toBeUndefined();
    });

    it("fallback 坏 JSON 时忽略并继续", async () => {
      getChatSessionMock.mockResolvedValue(null);
      localStorage.setItem("cs.conv.__fallback__", "{not json");
      const r = await loadResumeContext();
      expect(r.resume).toBeUndefined();
    });

    it("bridge 抛错时降级到 null（fallback 路径）", async () => {
      getChatSessionMock.mockRejectedValue(new Error("bridge crashed"));
      localStorage.setItem(
        "cs.conv.__fallback__",
        JSON.stringify({ id: 11, ts: Date.now() }),
      );
      const r = await loadResumeContext();
      expect(r.sessionId).toBeNull();
      expect(r.resume).toBe(11);
    });
  });

  describe("persistConversation 写入", () => {
    it("有 sessionId 时按 sessionId 写", () => {
      persistConversation("sess-1", 42);
      expect(localStorage.getItem("cs.conv.sess-1")).toBe("42");
    });
    it("无 sessionId 时写 fallback 含 ts", () => {
      persistConversation(null, 7);
      const v = JSON.parse(localStorage.getItem("cs.conv.__fallback__") ?? "{}");
      expect(v.id).toBe(7);
      expect(typeof v.ts).toBe("number");
    });
  });

  describe("touchFallback 刷新时间戳", () => {
    it("更新 ts 不动 id", () => {
      const past = Date.now() - 10 * 60_000;
      localStorage.setItem(
        "cs.conv.__fallback__",
        JSON.stringify({ id: 5, ts: past }),
      );
      touchFallback(5);
      const v = JSON.parse(localStorage.getItem("cs.conv.__fallback__") ?? "{}");
      expect(v.id).toBe(5);
      expect(v.ts).toBeGreaterThan(past);
    });
  });
});
