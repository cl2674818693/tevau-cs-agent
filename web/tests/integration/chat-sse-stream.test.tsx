// SSE 流端到端剧本（integration 层）：
//   把 streamChat 的真实生成器 + chatEvents 的 reducer 串起来，
//   验证一个完整 "用户发问 → message_start → 多次 delta → 工具调用/结果 → message_stop"
//   的链路是否能正确装配出最终的 Message[] 状态。
// 区别于 unit/lib/chatApi 与 unit/hooks/chatEvents：
//   - 那两个测纯函数；这里测两者拼接的端到端行为，是真正的"剧本"

import { describe, expect, it, vi } from "vitest";

import { streamChat } from "@/api/chat";
import { handleStreamEvent, type ChatActions } from "@/hooks/chatEvents";
import type { Message } from "@/types";

import { sseResponse } from "../helpers/sse";

function stubFetch(resp: Response) {
  // @ts-expect-error overwrite global
  globalThis.fetch = vi.fn(async () => resp);
}

describe("integration: SSE → reducer 端到端剧本", () => {
  it("happy path：累积内容 + 工具 ok + 不重复推 system", async () => {
    const frames = [
      "event: message_start\r\ndata: {\"message_id\":\"m1\"}\r\n\r\n",
      "event: content_block_delta\r\ndata: {\"index\":0,\"delta\":{\"type\":\"text_delta\",\"text\":\"你\"}}\r\n\r\n",
      "event: content_block_delta\r\ndata: {\"index\":0,\"delta\":{\"type\":\"text_delta\",\"text\":\"好\"}}\r\n\r\n",
      "event: tool_use\r\ndata: {\"tool_use_id\":\"t1\",\"name\":\"q\",\"input\":{}}\r\n\r\n",
      "event: tool_result\r\ndata: {\"tool_use_id\":\"t1\",\"name\":\"q\",\"is_error\":false}\r\n\r\n",
      "event: message_stop\r\ndata: {\"stop_reason\":\"end_turn\"}\r\n\r\n",
    ];
    stubFetch(sseResponse(frames));

    let msgs: Message[] = [];
    const actions: ChatActions = {
      setMode: vi.fn(),
      setMessages: (fn) => {
        msgs = fn(msgs);
      },
      setLimitPct: vi.fn(),
      setRateLimited: vi.fn(),
      onAuthExpired: vi.fn(),
    };

    for await (const ev of streamChat({ conversationId: 1, message: "hi" })) {
      await handleStreamEvent(ev, actions);
    }
    const a = msgs[0] as Extract<Message, { role: "assistant" }>;
    expect(a.role).toBe("assistant");
    expect(a.content).toBe("你好");
    expect(a.tool_calls?.[0]).toMatchObject({ name: "q", ok: true });
  });

  it("流中途出现 RATE_LIMITED → 设 rateLimited + 推系统消息 + 剥空 assistant 占位", async () => {
    const frames = [
      "event: message_start\r\ndata: {\"message_id\":\"m1\"}\r\n\r\n",
      "event: error\r\ndata: {\"code\":\"RATE_LIMITED\",\"message\":\"歇歇\"}\r\n\r\n",
    ];
    stubFetch(sseResponse(frames));

    let msgs: Message[] = [{ role: "system", content: "你好" }];
    const setRateLimited = vi.fn();
    const actions: ChatActions = {
      setMode: vi.fn(),
      setMessages: (fn) => {
        msgs = fn(msgs);
      },
      setLimitPct: vi.fn(),
      setRateLimited,
      onAuthExpired: vi.fn(),
    };

    for await (const ev of streamChat({ conversationId: 1, message: "hi" })) {
      await handleStreamEvent(ev, actions);
    }
    expect(setRateLimited).toHaveBeenCalledWith(true);
    expect(msgs).toEqual([
      { role: "system", content: "你好" },
      { role: "system", content: "歇歇" },
    ]);
  });

  it("warning 事件：更新 limitPct + 推系统消息", async () => {
    const frames = [
      "event: warning\r\ndata: {\"pct\":85,\"text\":\"用量 85%\"}\r\n\r\n",
    ];
    stubFetch(sseResponse(frames));
    let msgs: Message[] = [];
    const setLimitPct = vi.fn();
    const actions: ChatActions = {
      setMode: vi.fn(),
      setMessages: (fn) => {
        msgs = fn(msgs);
      },
      setLimitPct,
      setRateLimited: vi.fn(),
      onAuthExpired: vi.fn(),
    };
    for await (const ev of streamChat({ conversationId: 1, message: "hi" })) {
      await handleStreamEvent(ev, actions);
    }
    expect(setLimitPct).toHaveBeenCalledWith(85);
    expect(msgs).toEqual([{ role: "system", content: "用量 85%" }]);
  });
});
