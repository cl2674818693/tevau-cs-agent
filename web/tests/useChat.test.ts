import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const { requestHumanMock, cancelMock } = vi.hoisted(() => ({
  requestHumanMock: vi.fn(async () => {}),
  cancelMock: vi.fn(async () => {}),
}));

vi.mock("../src/api/chat", () => ({
  initConversation: async () => ({
    conversation_id: 42,
    user_type: "b",
    display_name: "BU00243780",
    greeting: "您好",
    history_url: null,
    limits: { daily_token_used_pct: 0, max_turns: 20 },
  }),
  streamChat: async function* () {
    yield { type: "message_start", message_id: "m1" };
    yield { type: "tool_use", name: "search_code", input: { q: "x" }, _eventId: "1" };
    yield { type: "tool_result", name: "search_code", is_error: false };
    yield { type: "content_block_delta", index: 0, delta: { type: "text_delta", text: "你" } };
    yield { type: "content_block_delta", index: 0, delta: { type: "text_delta", text: "好" } };
  },
  streamConversationMessages: async function* () {},
  requestHuman: requestHumanMock,
  cancelStream: cancelMock,
}));

import { useChat } from "../src/hooks/useChat";

describe("useChat", () => {
  it("adds assistant bubble on message_start, accumulates deltas + tool calls", async () => {
    const { result } = renderHook(() => useChat());
    await waitFor(() => expect(result.current.init).toBeTruthy());
    await act(async () => {
      await result.current.send("hi");
    });
    await waitFor(() => {
      const last = result.current.messages.at(-1) as {
        role: string;
        content: string;
        tool_calls?: { name: string; ok?: boolean }[];
      };
      expect(last.role).toBe("assistant");
      expect(last.content).toBe("你好");
      expect(last.tool_calls?.[0]).toMatchObject({ name: "search_code", ok: true });
    });
  });

  it("requestHandoff calls /request-human and sets human_pending", async () => {
    const { result } = renderHook(() => useChat());
    await waitFor(() => expect(result.current.init).toBeTruthy());
    await act(async () => {
      await result.current.requestHandoff();
    });
    expect(requestHumanMock).toHaveBeenCalledWith(42);
    expect(result.current.mode).toBe("human_pending");
  });
});
