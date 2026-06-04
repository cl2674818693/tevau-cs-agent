// useChat：聊天主 hook 集成行为。
// 用 vi.mock 整体替换 chat / identity / chatSession，避免 ESM live binding 在不同环境下的不确定性。
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { clearLocalStorage } from "../../_helpers/storage";

// ---- 顶层 mock：必须在被测模块 import 前完成 ----
const initConversation = vi.fn();
const fetchHistory = vi.fn();
const streamChatImpl = vi.fn();
const streamConversationMessagesImpl = vi.fn();
const cancelStream = vi.fn();
const requestHuman = vi.fn();
const reportClientInfo = vi.fn();

vi.mock("@/api/chat", () => ({
  initConversation: (...a: unknown[]) => initConversation(...a),
  fetchHistory: (...a: unknown[]) => fetchHistory(...a),
  streamChat: (a: unknown) => streamChatImpl(a),
  streamConversationMessages: (a: unknown) => streamConversationMessagesImpl(a),
  cancelStream: (...a: unknown[]) => cancelStream(...a),
  requestHuman: (...a: unknown[]) => requestHuman(...a),
  reportClientInfo: (...a: unknown[]) => reportClientInfo(...a),
  streamTicketEvents: () =>
    (async function* () {
      await new Promise(() => {});
    })(),
}));

const loadResumeContext = vi.fn();
const persistConversation = vi.fn();
const touchFallback = vi.fn();
vi.mock("@/lib/chatSession", () => ({
  loadResumeContext: () => loadResumeContext(),
  persistConversation: (...a: unknown[]) => persistConversation(...a),
  touchFallback: (...a: unknown[]) => touchFallback(...a),
}));

const resolveIdentity = vi.fn();
const userType = vi.fn();
vi.mock("@/api/identity", () => {
  // 必须在 factory 内定义 AuthExpiredError，避免 vi.mock 提升导致 TDZ。
  class AuthExpiredError extends Error {
    constructor() {
      super("auth expired");
      this.name = "AuthExpiredError";
    }
  }
  return {
    resolveIdentity: () => resolveIdentity(),
    userType: () => userType(),
    AuthExpiredError,
    authHeaders: async () => ({}),
    setIdentity: () => {},
    isLoggedIn: async () => true,
  };
});

// 测试代码里用的 AuthExpiredError：通过动态 import 再获取（在 vi.mock 替换后）。
let AuthExpiredErrorClass!: new () => Error;
beforeAll(async () => {
  AuthExpiredErrorClass = (await import("@/api/identity")).AuthExpiredError;
});

const syncLanguageFromBridge = vi.fn().mockResolvedValue(undefined);
vi.mock("@/i18n", async () => {
  const actual = await vi.importActual<typeof import("@/i18n")>("@/i18n");
  return {
    ...actual,
    default: actual.default,
    syncLanguageFromBridge: () => syncLanguageFromBridge(),
  };
});

vi.mock("@/hooks/useAppBridge", () => ({
  bridge: {
    whenReady: async () => true,
    getToken: async () => "tk",
    getChatSession: async () => null,
    getEnv: async () => ({ platform: "ios", version: "1.0.0" }),
    logout: async () => {},
    navigate: async () => {},
  },
}));

// ---- 测试代码 ----
import { useChat } from "@/hooks/useChat";

const INIT_INFO = {
  conversation_id: 100,
  user_type: "c" as const,
  display_name: "U",
  greeting: "你好",
  mode: "ai" as const,
  history_url: null,
  limits: { daily_token_used_pct: 0, max_turns: 30 },
};

/** 构造可手动控制的 SSE 生成器。 */
function controlled() {
  const queue: unknown[] = [];
  let resolve: ((v: unknown) => void) | null = null;
  let closed = false;
  let pendingError: unknown = null;
  const gen = (async function* () {
    while (!closed) {
      if (pendingError) {
        const e = pendingError;
        pendingError = null;
        throw e;
      }
      if (queue.length > 0) {
        yield queue.shift()!;
        continue;
      }
      await new Promise((r) => {
        resolve = r;
      });
    }
  })();
  return {
    gen,
    push(ev: unknown) {
      queue.push(ev);
      if (resolve) {
        const r = resolve;
        resolve = null;
        r(undefined);
      }
    },
    fail(err: unknown) {
      pendingError = err;
      if (resolve) {
        const r = resolve;
        resolve = null;
        r(undefined);
      }
    },
    close() {
      closed = true;
      if (resolve) {
        const r = resolve;
        resolve = null;
        r(undefined);
      }
    },
  };
}

function emptyStream() {
  return (async function* () {
    await new Promise(() => {});
  })();
}

describe("useChat", () => {
  beforeEach(() => {
    clearLocalStorage();
    initConversation.mockReset().mockResolvedValue(INIT_INFO);
    fetchHistory.mockReset().mockResolvedValue([]);
    streamChatImpl.mockReset().mockImplementation(() => emptyStream());
    streamConversationMessagesImpl.mockReset().mockImplementation(() => emptyStream());
    cancelStream.mockReset().mockResolvedValue(undefined);
    requestHuman.mockReset().mockResolvedValue(undefined);
    reportClientInfo.mockReset().mockResolvedValue(undefined);
    loadResumeContext.mockReset().mockResolvedValue({ sessionId: "s1", resume: undefined });
    persistConversation.mockReset();
    touchFallback.mockReset();
    resolveIdentity.mockReset().mockResolvedValue({ kind: "c" });
    userType.mockReset().mockReturnValue("c");
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("init 成功后 status=ready + messages 不含 greeting（greeting 由 EmptyState 走前端 i18n）", async () => {
    const { result } = renderHook(() => useChat());
    await waitFor(() => expect(result.current.status).toBe("ready"));
    expect(result.current.messages).toEqual([]);
    expect(result.current.init?.conversation_id).toBe(100);
  });

  it("init 失败：status=error；retryInit 可恢复", async () => {
    initConversation.mockRejectedValueOnce(new Error("boom"));
    const { result } = renderHook(() => useChat());
    await waitFor(() => expect(result.current.status).toBe("error"));
    await act(async () => {
      await result.current.retryInit();
    });
    expect(result.current.status).toBe("ready");
  });

  it("续接成功（resume == init.conversation_id）时回灌 history", async () => {
    loadResumeContext.mockResolvedValue({ sessionId: "s1", resume: 100 });
    initConversation.mockResolvedValue({ ...INIT_INFO, history_url: "/h/100" });
    fetchHistory.mockResolvedValue([{ role: "user", content: "上次说的" }]);
    const { result } = renderHook(() => useChat());
    await waitFor(() => expect(result.current.status).toBe("ready"));
    // greeting 不再塞 messages：续接只回灌 history 本身
    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0]).toMatchObject({ role: "user", content: "上次说的" });
  });

  it("新会话（resume != init.conversation_id）时不回灌 history", async () => {
    loadResumeContext.mockResolvedValue({ sessionId: "s1", resume: 99 });
    const { result } = renderHook(() => useChat());
    await waitFor(() => expect(result.current.status).toBe("ready"));
    expect(fetchHistory).not.toHaveBeenCalled();
    // greeting 不再塞 messages：新会话起始为空
    expect(result.current.messages).toHaveLength(0);
  });

  describe("send", () => {
    it("先追加 user 行 → SSE 累积 → 完成后 sending=false", async () => {
      const s = controlled();
      streamChatImpl.mockImplementationOnce(() => s.gen);
      const { result } = renderHook(() => useChat());
      await waitFor(() => expect(result.current.status).toBe("ready"));
      // 启动 send 但不 await（send 要等 SSE 闭合）；用 promise 句柄在末尾收尾。
      let p!: Promise<void>;
      await act(async () => {
        p = result.current.send("你好");
      });
      await waitFor(() =>
        expect(
          result.current.messages.some((m) => m.role === "user" && m.content === "你好"),
        ).toBe(true),
      );
      expect(result.current.sending).toBe(true);
      await act(async () => {
        s.push({ type: "message_start", message_id: "m" });
        // 给 for-await 一帧消费 message_start
        await new Promise((r) => setTimeout(r, 0));
        s.push({
          type: "content_block_delta",
          index: 0,
          delta: { type: "text_delta", text: "好的" },
        });
        await new Promise((r) => setTimeout(r, 0));
        s.close();
        await p;
      });
      expect(result.current.sending).toBe(false);
      const last = result.current.messages[result.current.messages.length - 1];
      expect(last).toMatchObject({ role: "assistant", content: "好的" });
    });

    it("RATE_LIMITED：置 rateLimited + 推系统提示 + 后续 send 短路", async () => {
      const s = controlled();
      streamChatImpl.mockImplementationOnce(() => s.gen);
      const { result } = renderHook(() => useChat());
      await waitFor(() => expect(result.current.status).toBe("ready"));
      let p!: Promise<void>;
      await act(async () => {
        p = result.current.send("x");
      });
      await act(async () => {
        s.push({ type: "error", code: "RATE_LIMITED", message: "慢点" });
        await new Promise((r) => setTimeout(r, 0));
        s.close();
        await p;
      });
      expect(result.current.rateLimited).toBe(true);
      streamChatImpl.mockClear();
      await act(async () => {
        await result.current.send("再来");
      });
      expect(streamChatImpl).not.toHaveBeenCalled();
    });

    it("AUTH_EXPIRED 事件：C 端 connection=reconnecting", async () => {
      const s = controlled();
      streamChatImpl.mockImplementationOnce(() => s.gen);
      const { result } = renderHook(() => useChat());
      await waitFor(() => expect(result.current.status).toBe("ready"));
      let p!: Promise<void>;
      await act(async () => {
        p = result.current.send("x");
      });
      await act(async () => {
        s.push({ type: "error", code: "AUTH_EXPIRED", message: "" });
        await new Promise((r) => setTimeout(r, 0));
        s.close();
        await p;
      });
      expect(result.current.connection).toBe("reconnecting");
    });

    it("AuthExpiredError 抛出 → 同样触发 onAuthExpired（C 端 reconnecting）", async () => {
      streamChatImpl.mockImplementationOnce(() => {
        throw new AuthExpiredErrorClass();
      });
      const { result } = renderHook(() => useChat());
      await waitFor(() => expect(result.current.status).toBe("ready"));
      await act(async () => {
        await result.current.send("x");
      });
      expect(result.current.connection).toBe("reconnecting");
    });

    it("普通错误：推系统提示", async () => {
      streamChatImpl.mockImplementationOnce(() => {
        throw new Error("net dead");
      });
      const { result } = renderHook(() => useChat());
      await waitFor(() => expect(result.current.status).toBe("ready"));
      await act(async () => {
        await result.current.send("x");
      });
      const last = result.current.messages[result.current.messages.length - 1];
      expect(last.role).toBe("system");
    });

    it("attachmentIds 渲染为 user.attachments", async () => {
      const s = controlled();
      streamChatImpl.mockImplementationOnce(() => s.gen);
      const { result } = renderHook(() => useChat());
      await waitFor(() => expect(result.current.status).toBe("ready"));
      let p!: Promise<void>;
      await act(async () => {
        p = result.current.send("看图", [1, 2]);
      });
      const user = result.current.messages.find((m) => m.role === "user") as {
        attachments?: { id: number }[];
      };
      expect(user.attachments?.map((a) => a.id)).toEqual([1, 2]);
      await act(async () => {
        s.close();
        await p;
      });
    });
  });

  it("stop：abort + cancelStream + 复位 sending", async () => {
    const s = controlled();
    streamChatImpl.mockImplementationOnce(() => s.gen);
    const { result } = renderHook(() => useChat());
    await waitFor(() => expect(result.current.status).toBe("ready"));
    let p!: Promise<void>;
    await act(async () => {
      p = result.current.send("x");
    });
    expect(result.current.sending).toBe(true);
    await act(async () => {
      result.current.stop();
      s.close();
      await p.catch(() => {});
    });
    expect(result.current.sending).toBe(false);
    expect(cancelStream).toHaveBeenCalledWith(100);
  });

  describe("requestHandoff", () => {
    it("正常用户：调 requestHuman + 切到 human_pending", async () => {
      const { result } = renderHook(() => useChat());
      await waitFor(() => expect(result.current.status).toBe("ready"));
      await act(async () => {
        await result.current.requestHandoff();
      });
      expect(requestHuman).toHaveBeenCalledWith(100);
      expect(result.current.mode).toBe("human_pending");
    });

    it("游客（user_type=g）：不调后端 + 提示在 APP 登录", async () => {
      initConversation.mockResolvedValue({ ...INIT_INFO, user_type: "g" });
      const { result } = renderHook(() => useChat());
      await waitFor(() => expect(result.current.status).toBe("ready"));
      await act(async () => {
        await result.current.requestHandoff();
      });
      expect(requestHuman).not.toHaveBeenCalled();
      const last = result.current.messages[result.current.messages.length - 1];
      expect(last).toMatchObject({ role: "system" });
      expect((last as { content: string }).content).toMatch(/APP/);
    });
  });

  it("常驻流 mode_change=human_takeover 推系统提示", async () => {
    const s = controlled();
    streamConversationMessagesImpl.mockImplementationOnce(() => s.gen);
    const { result } = renderHook(() => useChat());
    await waitFor(() => expect(result.current.status).toBe("ready"));
    await act(async () => {
      s.push({ type: "mode_change", to: "human_takeover" });
      // 让 for-await 跑一帧
      await new Promise((r) => setTimeout(r, 10));
    });
    expect(result.current.mode).toBe("human_takeover");
    const last = result.current.messages[result.current.messages.length - 1];
    expect((last as { content: string }).content).toMatch(/客服/);
    s.close();
  });

  it("常驻流断开后退避重连（第二次调用 streamConversationMessages）", async () => {
    const s1 = controlled();
    const s2 = controlled();
    streamConversationMessagesImpl
      .mockImplementationOnce(() => s1.gen)
      .mockImplementationOnce(() => s2.gen);
    const { result } = renderHook(() => useChat());
    await waitFor(() => expect(result.current.status).toBe("ready"));
    s1.fail(new Error("net"));
    await waitFor(
      () => expect(streamConversationMessagesImpl.mock.calls.length).toBeGreaterThanOrEqual(2),
      { timeout: 3000 },
    );
  });

  describe("B 端 AUTH_EXPIRED 跳登录", () => {
    let originalLocation: Location;
    let hrefSetter: ReturnType<typeof vi.fn>;
    beforeEach(() => {
      originalLocation = window.location;
      hrefSetter = vi.fn();
      Object.defineProperty(window, "location", {
        configurable: true,
        writable: true,
        value: {
          ...originalLocation,
          pathname: "/",
          get href() {
            return "x";
          },
          set href(v: string) {
            hrefSetter(v);
          },
        },
      });
      userType.mockReturnValue("b");
    });
    afterEach(() => {
      Object.defineProperty(window, "location", {
        configurable: true,
        writable: true,
        value: originalLocation,
      });
    });

    it("location.href = /bu/login", async () => {
      const s = controlled();
      streamChatImpl.mockImplementationOnce(() => s.gen);
      const { result } = renderHook(() => useChat());
      await waitFor(() => expect(result.current.status).toBe("ready"));
      let p!: Promise<void>;
      await act(async () => {
        p = result.current.send("x");
      });
      await act(async () => {
        s.push({ type: "error", code: "AUTH_EXPIRED", message: "" });
        await new Promise((r) => setTimeout(r, 0));
        s.close();
        await p;
      });
      expect(hrefSetter).toHaveBeenCalledWith("/bu/login");
    });
  });

  describe("online/offline", () => {
    it("offline 事件 → connection=offline；online → 复位", async () => {
      const { result } = renderHook(() => useChat());
      await waitFor(() => expect(result.current.status).toBe("ready"));
      await act(async () => {
        window.dispatchEvent(new Event("offline"));
      });
      expect(result.current.connection).toBe("offline");
      await act(async () => {
        window.dispatchEvent(new Event("online"));
      });
      expect(result.current.connection).toBe("online");
    });
  });
});
