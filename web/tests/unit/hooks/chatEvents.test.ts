// chatEvents 纯函数 + 主链路/常驻流派发逻辑测试。
// 重点：
// - event-driven 不乐观（不在本地额外 push 用户已知的字段，全靠 ev.content）
// - human_takeover 切换不再误推"请稍候"（修复点）
// - 错误事件先剥空 assistant 占位再 push 系统提示
import { describe, expect, it, vi } from "vitest";

import type { ChatActions, StaffStreamActions } from "@/hooks/chatEvents";
import {
  applyEvent,
  applyUserStreamEvent,
  handleStreamEvent,
  pushSystem,
} from "@/hooks/chatEvents";
import type { ChatEvent, Message } from "@/types";

describe("applyEvent 纯函数事件应用", () => {
  it("message_start 追加空 assistant 占位", () => {
    const prev: Message[] = [{ role: "system", content: "hi" }];
    const next = applyEvent(prev, { type: "message_start", message_id: "m1" } as ChatEvent);
    expect(next).toHaveLength(2);
    expect(next[1]).toMatchObject({ role: "assistant", content: "", tool_calls: [] });
  });

  it("content_block_delta 累加到最后一个 assistant", () => {
    const prev: Message[] = [{ role: "assistant", content: "你", tool_calls: [] }];
    const next = applyEvent(prev, {
      type: "content_block_delta",
      index: 0,
      delta: { type: "text_delta", text: "好" },
    } as ChatEvent);
    expect((next[0] as { content: string }).content).toBe("你好");
  });

  it("空 delta 文本兼容（不抛）", () => {
    const prev: Message[] = [{ role: "assistant", content: "a", tool_calls: [] }];
    const next = applyEvent(prev, {
      type: "content_block_delta",
      index: 0,
      delta: { type: "text_delta", text: "" },
    } as ChatEvent);
    expect((next[0] as { content: string }).content).toBe("a");
  });

  it("tool_use 追加 tool_call", () => {
    const prev: Message[] = [{ role: "assistant", content: "", tool_calls: [] }];
    const next = applyEvent(prev, {
      type: "tool_use",
      tool_use_id: "u1",
      name: "query_user",
      input: { id: 1 },
    } as ChatEvent);
    expect((next[0] as { tool_calls: unknown[] }).tool_calls).toEqual([
      { tool_use_id: "u1", name: "query_user", input: { id: 1 } },
    ]);
  });

  it("tool_result 按 tool_use_id 精确配对（并发不错配）", () => {
    const prev: Message[] = [
      {
        role: "assistant",
        content: "",
        tool_calls: [
          { tool_use_id: "u1", name: "a", input: {} },
          { tool_use_id: "u2", name: "b", input: {} },
        ],
      },
    ];
    const next = applyEvent(prev, {
      type: "tool_result",
      tool_use_id: "u2",
      name: "b",
      is_error: false,
    } as ChatEvent);
    const calls = (next[0] as { tool_calls: { tool_use_id: string; ok?: boolean }[] }).tool_calls;
    expect(calls[0].ok).toBeUndefined();
    expect(calls[1].ok).toBe(true);
  });

  it("tool_result 缺 id 时回退到最后一个 tool_call", () => {
    const prev: Message[] = [
      {
        role: "assistant",
        content: "",
        tool_calls: [
          { tool_use_id: "u1", name: "a", input: {} },
        ],
      },
    ];
    const next = applyEvent(prev, {
      type: "tool_result",
      name: "a",
      is_error: true,
    } as ChatEvent);
    const calls = (next[0] as { tool_calls: { ok?: boolean }[] }).tool_calls;
    expect(calls[0].ok).toBe(false);
  });

  it("human_message 追加 human_agent 行（含 display_name）", () => {
    const next = applyEvent([], {
      type: "human_message",
      content: "您好",
      display_name: "小王",
      attachments: [{ id: 1, mime: "image/jpeg" }],
    } as unknown as ChatEvent);
    expect(next[0]).toMatchObject({
      role: "human_agent",
      content: "您好",
      display_name: "小王",
      attachments: [{ id: 1, mime: "image/jpeg" }],
    });
  });

  it("assistant_message 追加 assistant 行（不带占位 tool_calls）", () => {
    const next = applyEvent([], {
      type: "assistant_message",
      content: "ok",
    } as unknown as ChatEvent);
    expect(next[0]).toMatchObject({ role: "assistant", content: "ok" });
  });

  it("未知事件类型不变更", () => {
    const prev: Message[] = [{ role: "system", content: "x" }];
    const next = applyEvent(prev, { type: "xxx" } as unknown as ChatEvent);
    expect(next).toBe(prev);
  });
});

describe("handleStreamEvent 主链路派发", () => {
  function mkActions(): ChatActions & { _messages: () => Message[] } {
    let msgs: Message[] = [];
    const fns = {
      setMode: vi.fn(),
      setLimitPct: vi.fn(),
      setRateLimited: vi.fn(),
      onAuthExpired: vi.fn<() => Promise<void>>().mockResolvedValue(),
      setMessages: (fn: (p: Message[]) => Message[]) => {
        msgs = fn(msgs);
      },
    };
    return Object.assign(fns, { _messages: () => msgs });
  }

  it("mode_change 只更新 mode，不再 push 系统提示（AI 在 create_ticket 回复里已说，避免重复）", async () => {
    // human_pending：mode 更新，无 system push
    let a = mkActions();
    await handleStreamEvent({ type: "mode_change", to: "human_pending" } as ChatEvent, a);
    expect(a.setMode).toHaveBeenCalledWith("human_pending");
    expect(a._messages()).toEqual([]);

    // human_takeover：客服早在线，更不该 push
    a = mkActions();
    await handleStreamEvent({ type: "mode_change", to: "human_takeover" } as ChatEvent, a);
    expect(a.setMode).toHaveBeenCalledWith("human_takeover");
    expect(a._messages()).toEqual([]);

    // ai：不 push
    a = mkActions();
    await handleStreamEvent({ type: "mode_change", to: "ai" } as ChatEvent, a);
    expect(a._messages()).toEqual([]);
  });

  it("warning 同步 limit pct 并 push 文本", async () => {
    const a = mkActions();
    await handleStreamEvent(
      { type: "warning", pct: 90, text: "已用 90%" } as unknown as ChatEvent,
      a,
    );
    expect(a.setLimitPct).toHaveBeenCalledWith(90);
    expect(a._messages()[0]).toMatchObject({ role: "system", content: "已用 90%" });
  });

  it("RATE_LIMITED 错误：置 rateLimited + 推提示 + 剥空 assistant 占位", async () => {
    const a = mkActions();
    a.setMessages(() => [{ role: "assistant", content: "", tool_calls: [] }]);
    await handleStreamEvent(
      { type: "error", code: "RATE_LIMITED", message: "慢点" } as ChatEvent,
      a,
    );
    expect(a.setRateLimited).toHaveBeenCalledWith(true);
    expect(a._messages()).toEqual([{ role: "system", content: "慢点" }]);
  });

  it("SYSTEM_BUSY 错误：推后端文案提示，但不锁死 sending（区别于 RATE_LIMITED）", async () => {
    const a = mkActions();
    a.setMessages(() => [{ role: "assistant", content: "", tool_calls: [] }]);
    await handleStreamEvent(
      { type: "error", code: "SYSTEM_BUSY", message: "系统繁忙，请稍后再试。" } as ChatEvent,
      a,
    );
    // 关键差异：SYSTEM_BUSY 不调 setRateLimited（不锁输入框）
    expect(a.setRateLimited).not.toHaveBeenCalled();
    expect(a._messages()).toEqual([{ role: "system", content: "系统繁忙，请稍后再试。" }]);
  });

  it("SYSTEM_BUSY 缺 message 时回退默认提示", async () => {
    const a = mkActions();
    await handleStreamEvent(
      { type: "error", code: "SYSTEM_BUSY", message: "" } as ChatEvent,
      a,
    );
    expect(a._messages()[0]).toMatchObject({ role: "system", content: "系统繁忙，请稍后再试。" });
  });

  it("AUTH_EXPIRED 错误调用 onAuthExpired", async () => {
    const a = mkActions();
    await handleStreamEvent(
      { type: "error", code: "AUTH_EXPIRED", message: "" } as ChatEvent,
      a,
    );
    expect(a.onAuthExpired).toHaveBeenCalled();
  });

  it("其它 error 推默认 fallback 提示", async () => {
    const a = mkActions();
    await handleStreamEvent({ type: "error", code: "X", message: "" } as ChatEvent, a);
    expect(a._messages()[0]).toMatchObject({ role: "system" });
  });

  it("普通事件转给 applyEvent", async () => {
    const a = mkActions();
    await handleStreamEvent({ type: "message_start", message_id: "m" } as ChatEvent, a);
    expect(a._messages()).toHaveLength(1);
    expect(a._messages()[0]).toMatchObject({ role: "assistant" });
  });
});

describe("applyUserStreamEvent 客服→用户常驻流派发", () => {
  function mkActions() {
    let msgs: Message[] = [];
    let mode = "ai";
    let staffName: string | undefined;
    return {
      get messages() {
        return msgs;
      },
      get mode() {
        return mode;
      },
      get staffName() {
        return staffName;
      },
      asActions(): StaffStreamActions {
        return {
          setMode: (m) => {
            mode = m;
          },
          setStaffName: (n) => {
            staffName = n;
          },
          setMessages: (fn) => {
            msgs = fn(msgs);
          },
        };
      },
    };
  }

  it("mode_change=human_takeover 推客服接入提示", () => {
    const a = mkActions();
    applyUserStreamEvent(
      { type: "mode_change", to: "human_takeover" } as ChatEvent,
      a.asActions(),
    );
    expect(a.mode).toBe("human_takeover");
    expect(a.messages[0]).toMatchObject({ role: "system", content: expect.stringContaining("客服") });
  });

  it("mode_change=ai 不推提示", () => {
    const a = mkActions();
    applyUserStreamEvent({ type: "mode_change", to: "ai" } as ChatEvent, a.asActions());
    expect(a.messages).toEqual([]);
  });

  it("human_message 同步 staff name 并 push 消息", () => {
    const a = mkActions();
    applyUserStreamEvent(
      {
        type: "human_message",
        content: "您好",
        display_name: "小王",
      } as unknown as ChatEvent,
      a.asActions(),
    );
    expect(a.staffName).toBe("小王");
    expect(a.messages[0]).toMatchObject({ role: "human_agent", content: "您好" });
  });

  it("human_message 缺 display_name 时回退 sender_staff_id", () => {
    const a = mkActions();
    applyUserStreamEvent(
      {
        type: "human_message",
        content: "x",
        sender_staff_id: "agent-9",
      } as unknown as ChatEvent,
      a.asActions(),
    );
    expect(a.staffName).toBe("agent-9");
  });

  it("transferred 推转派提示", () => {
    const a = mkActions();
    applyUserStreamEvent(
      { type: "transferred", to_staff_id: "x" } as ChatEvent,
      a.asActions(),
    );
    expect(a.messages[0]).toMatchObject({ role: "system" });
  });

  it("request_human 切到 human_pending + 推提示", () => {
    const a = mkActions();
    applyUserStreamEvent({ type: "request_human" } as ChatEvent, a.asActions());
    expect(a.mode).toBe("human_pending");
    expect(a.messages[0]).toMatchObject({ role: "system" });
  });

  it("assistant_message 通过 applyEvent push", () => {
    const a = mkActions();
    applyUserStreamEvent(
      { type: "assistant_message", content: "ai 回复" } as unknown as ChatEvent,
      a.asActions(),
    );
    expect(a.messages[0]).toMatchObject({ role: "assistant", content: "ai 回复" });
  });

  it("event-driven：不乐观；客服消息只从 SSE 来，不本地追加", () => {
    // 业务约束：用户/客服侧均通过 SSE 事件统一驱动；本函数除收到的事件外不应自造消息。
    const a = mkActions();
    applyUserStreamEvent({ type: "ping" } as unknown as ChatEvent, a.asActions());
    expect(a.messages).toEqual([]);
  });
});

describe("pushSystem helper", () => {
  it("用 setMessages 追加 system 行", () => {
    let msgs: Message[] = [{ role: "user", content: "x" }];
    const a: ChatActions = {
      setMode: vi.fn(),
      setLimitPct: vi.fn(),
      setRateLimited: vi.fn(),
      onAuthExpired: vi.fn<() => Promise<void>>().mockResolvedValue(),
      setMessages: (fn) => {
        msgs = fn(msgs);
      },
    };
    pushSystem(a, "提示");
    expect(msgs).toHaveLength(2);
    expect(msgs[1]).toMatchObject({ role: "system", content: "提示" });
  });
});
