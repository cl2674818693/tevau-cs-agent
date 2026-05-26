import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { getChatSessionMock } = vi.hoisted(() => ({
  getChatSessionMock: vi.fn<() => Promise<string | null>>(),
}));

vi.mock("../src/hooks/useAppBridge", () => ({
  bridge: { getChatSession: getChatSessionMock },
}));

import { loadResumeContext, persistConversation, touchFallback } from "../src/lib/chatSession";

const PREFIX = "cs.conv.";
const FALLBACK_KEY = "cs.conv.__fallback__";
const WINDOW_MS = 30 * 60 * 1000;

beforeEach(() => {
  // 该环境的全局 localStorage 不完整，按仓库惯例用 Map 支撑的 stub（含 length/key 供 prune 用）
  const store = new Map<string, string>();
  vi.stubGlobal("localStorage", {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, String(v)),
    removeItem: (k: string) => void store.delete(k),
    clear: () => store.clear(),
    get length() {
      return store.size;
    },
    key: (i: number) => Array.from(store.keys())[i] ?? null,
  });
  getChatSessionMock.mockReset();
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe("chatSession 主路径（有 sessionId）", () => {
  it("有映射 → 续接对应会话", async () => {
    getChatSessionMock.mockResolvedValue("sess-A");
    localStorage.setItem(PREFIX + "sess-A", "42");
    const ctx = await loadResumeContext();
    expect(ctx).toEqual({ sessionId: "sess-A", resume: 42 });
  });

  it("无映射 → 不续接（新建）", async () => {
    getChatSessionMock.mockResolvedValue("sess-new");
    const ctx = await loadResumeContext();
    expect(ctx).toEqual({ sessionId: "sess-new", resume: undefined });
  });

  it("清理其他 sessionId 的旧映射，保留当前与 fallback", async () => {
    getChatSessionMock.mockResolvedValue("sess-cur");
    localStorage.setItem(PREFIX + "sess-old", "7");
    localStorage.setItem(PREFIX + "sess-cur", "9");
    localStorage.setItem(FALLBACK_KEY, JSON.stringify({ id: 1, ts: Date.now() }));
    await loadResumeContext();
    expect(localStorage.getItem(PREFIX + "sess-old")).toBeNull();
    expect(localStorage.getItem(PREFIX + "sess-cur")).toBe("9");
    expect(localStorage.getItem(FALLBACK_KEY)).not.toBeNull();
  });

  it("persistConversation 按 sessionId 落映射", () => {
    persistConversation("sess-X", 99);
    expect(localStorage.getItem(PREFIX + "sess-X")).toBe("99");
  });
});

describe("降级路径（sessionId=null，时间窗）", () => {
  it("窗口内 → 续接", async () => {
    getChatSessionMock.mockResolvedValue(null);
    localStorage.setItem(FALLBACK_KEY, JSON.stringify({ id: 55, ts: Date.now() - 1000 }));
    const ctx = await loadResumeContext();
    expect(ctx).toEqual({ sessionId: null, resume: 55 });
  });

  it("超出窗口 → 新建", async () => {
    getChatSessionMock.mockResolvedValue(null);
    localStorage.setItem(FALLBACK_KEY, JSON.stringify({ id: 55, ts: Date.now() - WINDOW_MS - 1 }));
    const ctx = await loadResumeContext();
    expect(ctx).toEqual({ sessionId: null, resume: undefined });
  });

  it("无 fallback 记录 → 新建", async () => {
    getChatSessionMock.mockResolvedValue(null);
    const ctx = await loadResumeContext();
    expect(ctx).toEqual({ sessionId: null, resume: undefined });
  });

  it("persistConversation 写 fallback；touchFallback 刷新时间戳后仍在窗口内", async () => {
    getChatSessionMock.mockResolvedValue(null);
    vi.useFakeTimers();
    vi.setSystemTime(0);
    persistConversation(null, 77);
    // 时间推进到接近窗口边界，但 touch 后重置
    vi.setSystemTime(WINDOW_MS - 1000);
    touchFallback(77);
    vi.setSystemTime(WINDOW_MS + 100); // 距 persist 已超窗，但距 touch 未超
    const ctx = await loadResumeContext();
    expect(ctx.resume).toBe(77);
  });

  it("bridge 抛错 → 退到时间窗路径（sessionId=null）", async () => {
    getChatSessionMock.mockRejectedValue(new Error("no bridge"));
    const ctx = await loadResumeContext();
    expect(ctx.sessionId).toBeNull();
  });
});
