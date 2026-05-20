import { jsx as _jsx } from "react/jsx-runtime";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
vi.mock("../src/api/chat", () => ({
    initConversation: async () => ({
        conversation_id: 1,
        user_type: "b",
        display_name: "BU00243780",
        greeting: "您好",
        history_url: null,
        limits: { daily_token_used_pct: 0, max_turns: 20 },
    }),
    streamChat: async function* () {
        yield {
            type: "content_block_delta",
            index: 0,
            delta: { type: "text_delta", text: "已收到。" },
        };
    },
    cancelStream: async () => { },
}));
import { ChatWindow } from "../src/components/ChatWindow";
describe("ChatWindow", () => {
    it("sends a message and shows assistant reply", async () => {
        render(_jsx(ChatWindow, {}));
        const input = await screen.findByPlaceholderText("描述你的问题…");
        fireEvent.change(input, { target: { value: "hi" } });
        fireEvent.click(screen.getByLabelText("发送"));
        await waitFor(() => expect(screen.getByText("已收到。")).toBeTruthy());
    });
});
