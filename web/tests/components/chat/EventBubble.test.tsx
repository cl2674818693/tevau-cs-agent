// EventBubble：admin 详情页气泡（用户左、AI/客服右、工具用居中胶囊）。
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EventBubble, messageToStreamEvent } from "@/components/EventBubble";
import type { StaffMessage, StaffStreamEvent } from "@/api/staff";

const DEFAULTS = { convId: 1, token: "tk" };

describe("EventBubble", () => {
  it("user_message 渲染用户文字", () => {
    render(
      <EventBubble
        {...DEFAULTS}
        ev={{ type: "user_message", content: "你好啊" } as StaffStreamEvent}
      />,
    );
    expect(screen.getByText("你好啊")).toBeInTheDocument();
    expect(screen.getByText("用户")).toBeInTheDocument();
  });

  it("assistant_message 走 markdown 渲染（粗体）", () => {
    render(
      <EventBubble
        {...DEFAULTS}
        ev={{ type: "assistant_message", content: "**重要**" } as StaffStreamEvent}
      />,
    );
    const strong = screen.getByText("重要");
    expect(strong.tagName.toLowerCase()).toBe("strong");
  });

  it("assistant_text 与 assistant_message 同样处理", () => {
    render(
      <EventBubble
        {...DEFAULTS}
        ev={{ type: "assistant_text", content: "x" } as unknown as StaffStreamEvent}
      />,
    );
    expect(screen.getByText("x")).toBeInTheDocument();
  });

  it("human_message：客服气泡（右侧，标签'客服'）", () => {
    render(
      <EventBubble
        {...DEFAULTS}
        ev={{ type: "human_message", content: "您好我是客服" } as StaffStreamEvent}
      />,
    );
    expect(screen.getByText("您好我是客服")).toBeInTheDocument();
    expect(screen.getByText("客服")).toBeInTheDocument();
  });

  it("tool_use：居中胶囊显示工具名 + 截断的 input", () => {
    render(
      <EventBubble
        {...DEFAULTS}
        ev={{ type: "tool_use", name: "query_user", input: { id: 1 } } as StaffStreamEvent}
      />,
    );
    expect(screen.getByText(/query_user/)).toBeInTheDocument();
  });

  it("tool_result 失败：warning 色，标'失败'", () => {
    render(
      <EventBubble
        {...DEFAULTS}
        ev={{ type: "tool_result", name: "x", ok: false, result_count: 0 } as StaffStreamEvent}
      />,
    );
    expect(screen.getByText(/失败/)).toBeInTheDocument();
  });

  it("tool_result 空结果", () => {
    render(
      <EventBubble
        {...DEFAULTS}
        ev={
          { type: "tool_result", name: "x", ok: true, empty: true, result_count: 0 } as StaffStreamEvent
        }
      />,
    );
    expect(screen.getByText(/空/)).toBeInTheDocument();
  });

  it("mode_change：显示中文模式名", () => {
    render(
      <EventBubble
        {...DEFAULTS}
        ev={{ type: "mode_change", to: "human_takeover" } as StaffStreamEvent}
      />,
    );
    expect(screen.getByText(/人工接管/)).toBeInTheDocument();
  });

  it("transferred：显示转派目标", () => {
    render(
      <EventBubble
        {...DEFAULTS}
        ev={{ type: "transferred", to_staff_id: "a-9" } as StaffStreamEvent}
      />,
    );
    expect(screen.getByText(/a-9/)).toBeInTheDocument();
  });

  it("request_human：警示胶囊", () => {
    render(
      <EventBubble
        {...DEFAULTS}
        ev={{ type: "request_human" } as StaffStreamEvent}
      />,
    );
    expect(screen.getByText(/请求人工/)).toBeInTheDocument();
  });

  it("ai_draft_ready：muted 胶囊", () => {
    render(
      <EventBubble
        {...DEFAULTS}
        ev={{ type: "ai_draft_ready" } as StaffStreamEvent}
      />,
    );
    expect(screen.getByText(/草稿已就绪/)).toBeInTheDocument();
  });

  it("error 事件：红色胶囊", () => {
    render(
      <EventBubble
        {...DEFAULTS}
        ev={{ type: "error", content: "boom" } as StaffStreamEvent}
      />,
    );
    expect(screen.getByText(/错误：boom/)).toBeInTheDocument();
  });

  it("未知事件：兜底显示 [type] 内容", () => {
    render(
      <EventBubble
        {...DEFAULTS}
        ev={{ type: "pending_takeover_timeout", content: "超时" } as StaffStreamEvent}
      />,
    );
    expect(screen.getByText(/pending_takeover_timeout/)).toBeInTheDocument();
  });
});

describe("messageToStreamEvent", () => {
  it("user/assistant/human_agent → 对应事件 type", () => {
    const u = messageToStreamEvent({ id: 1, role: "user", content: "a" } as StaffMessage);
    expect(u?.type).toBe("user_message");
    const a = messageToStreamEvent({ id: 2, role: "assistant", content: "b" } as StaffMessage);
    expect(a?.type).toBe("assistant_message");
    const h = messageToStreamEvent({ id: 3, role: "human_agent", content: "c" } as StaffMessage);
    expect(h?.type).toBe("human_message");
  });

  it("ai_draft 或未知 role → null", () => {
    expect(
      messageToStreamEvent({ id: 4, role: "ai_draft", content: "x" } as StaffMessage),
    ).toBeNull();
    expect(
      messageToStreamEvent({ id: 5, role: "weird", content: "x" } as StaffMessage),
    ).toBeNull();
  });

  it("不填 draft（避免被 useAiDraft 误判为新草稿）", () => {
    const a = messageToStreamEvent({ id: 1, role: "assistant", content: "x" } as StaffMessage);
    expect(a).not.toHaveProperty("draft");
  });
});
