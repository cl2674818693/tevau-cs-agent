import { describe, expect, it, vi } from "vitest";

import { applyUserStreamEvent, handleStreamEvent } from "../src/hooks/chatEvents";
import type { ChatEvent, Message } from "../src/types";

function harness() {
  let messages: Message[] = [];
  const setMode = vi.fn();
  const setStaffName = vi.fn();
  const setMessages = (fn: (p: Message[]) => Message[]) => {
    messages = fn(messages);
  };
  return { actions: { setMode, setStaffName, setMessages }, get: () => messages, setMode };
}

function systemMatching(messages: Message[], needle: string): Message[] {
  return messages.filter((m) => m.role === "system" && m.content.includes(needle));
}

describe("applyUserStreamEvent", () => {
  it("request_human 只产生一条「已为您请求人工」提示（不与本地乐观重复）", () => {
    const h = harness();
    applyUserStreamEvent({ type: "request_human", ticket_id: "T1" } as unknown as ChatEvent, h.actions);
    expect(systemMatching(h.get(), "已为您请求人工")).toHaveLength(1);
    expect(h.setMode).toHaveBeenCalledWith("human_pending");
  });

  it("mode_change 到 human_takeover 追加一条「客服已接入」提示", () => {
    const h = harness();
    applyUserStreamEvent({ type: "mode_change", to: "human_takeover" } as unknown as ChatEvent, h.actions);
    expect(systemMatching(h.get(), "客服已接入")).toHaveLength(1);
    expect(h.setMode).toHaveBeenCalledWith("human_takeover");
  });

  it("mode_change 到 ai 只切 mode、不追加提示", () => {
    const h = harness();
    applyUserStreamEvent({ type: "mode_change", to: "ai" } as unknown as ChatEvent, h.actions);
    expect(h.get()).toHaveLength(0);
    expect(h.setMode).toHaveBeenCalledWith("ai");
  });
});

describe("handleStreamEvent error", () => {
  it("回合出错时剥掉尾部空 assistant 占位气泡，只留错误提示", async () => {
    let messages: Message[] = [
      { role: "user", content: "你好" },
      { role: "assistant", content: "", tool_calls: [] }, // message_start 占位
    ];
    const actions = {
      setMode: vi.fn(),
      setMessages: (fn: (p: Message[]) => Message[]) => {
        messages = fn(messages);
      },
      setLimitPct: vi.fn(),
      setRateLimited: vi.fn(),
      onAuthExpired: vi.fn(async () => {}),
    };
    await handleStreamEvent(
      { type: "error", code: "INTERNAL_ERROR", message: "出错了" } as unknown as ChatEvent,
      actions,
    );
    expect(messages.some((m) => m.role === "assistant" && !m.content)).toBe(false);
    expect(messages.filter((m) => m.role === "system")).toHaveLength(1);
  });
});
