import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
const { cancelMock } = vi.hoisted(() => ({ cancelMock: vi.fn(async () => { }) }));
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
        yield { type: "tool_use", name: "search_code", input: { q: "x" }, _eventId: "1" };
        yield { type: "tool_result", name: "search_code", is_error: false };
        yield { type: "content_block_delta", index: 0, delta: { type: "text_delta", text: "你" } };
        yield { type: "content_block_delta", index: 0, delta: { type: "text_delta", text: "好" } };
        yield { type: "error", code: "INTERNAL_ERROR", message: "ignored" };
    },
    cancelStream: cancelMock,
}));
import { HANDOFF_TRIGGER_TEXT, useChat } from "../src/hooks/useChat";
describe("useChat", () => {
    it("accumulates deltas and records tool calls into the assistant bubble", async () => {
        const { result } = renderHook(() => useChat());
        await waitFor(() => expect(result.current.init).toBeTruthy());
        await act(async () => {
            await result.current.send("hi");
        });
        await waitFor(() => {
            const last = result.current.messages.at(-1);
            expect(last.role).toBe("assistant");
            expect(last.content).toBe("你好");
            expect(last.tool_calls?.[0]).toMatchObject({ name: "search_code", ok: true });
        });
    });
    it("requestHandoff sends the fixed handoff text; stop calls cancelStream", async () => {
        const { result } = renderHook(() => useChat());
        await waitFor(() => expect(result.current.init).toBeTruthy());
        await act(async () => {
            await result.current.requestHandoff();
        });
        expect(result.current.messages.some((m) => "content" in m && m.content === HANDOFF_TRIGGER_TEXT)).toBe(true);
        act(() => result.current.stop());
        expect(cancelMock).toHaveBeenCalledWith(42, "BU00243780");
    });
});
