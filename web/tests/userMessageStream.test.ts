import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../src/api/chat", () => ({
  initConversation: async () => ({
    conversation_id: 7,
    user_type: "b",
    display_name: "BU1",
    greeting: "您好",
    history_url: null,
    limits: { daily_token_used_pct: 0, max_turns: 20 },
  }),
  streamChat: async function* () {},
  // 常驻流：客服接管 → 回复 → ai_draft 审核通过
  streamConversationMessages: async function* () {
    yield { type: "mode_change", to: "human_takeover" };
    yield { type: "human_message", content: "客服已为您处理", sender_staff_id: "S1" };
    yield { type: "assistant_message", content: "审核通过的草稿答复" };
  },
  requestHuman: async () => {},
  cancelStream: async () => {},
}));

import { useChat } from "../src/hooks/useChat";

describe("useChat 用户侧常驻消息流", () => {
  it("接收客服回复 / 审核草稿并更新 mode", async () => {
    const { result } = renderHook(() => useChat());
    await waitFor(() => expect(result.current.init).toBeTruthy());

    await waitFor(() => expect(result.current.mode).toBe("human_takeover"));
    await waitFor(() => {
      const roles = result.current.messages.map((m) => m.role);
      expect(roles).toContain("human_agent");
      expect(roles).toContain("assistant");
    });
    const human = result.current.messages.find((m) => m.role === "human_agent");
    const asst = result.current.messages.find((m) => m.role === "assistant");
    expect(human?.content).toBe("客服已为您处理");
    expect(asst?.content).toBe("审核通过的草稿答复");
    // 接管时给用户明确的「客服已接入」提示，避免停留在「请求人工，请稍候」
    const intro = result.current.messages.filter(
      (m) => m.role === "system" && m.content.includes("客服已接入"),
    );
    expect(intro).toHaveLength(1);
  });
});
