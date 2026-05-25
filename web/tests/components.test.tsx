import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { HandoffPrompt } from "../src/components/HandoffButton";
import { MessageBubble } from "../src/components/MessageBubble";
import { TicketCard } from "../src/components/TicketCard";
import { ToolCallChip } from "../src/components/ToolCallChip";

describe("MessageBubble", () => {
  it("renders user message right-aligned", () => {
    render(<MessageBubble m={{ role: "user", content: "你好啊" }} />);
    expect(screen.getByText("你好啊")).toBeTruthy();
  });

  it("renders system greeting", () => {
    render(<MessageBubble m={{ role: "system", content: "欢迎" }} />);
    expect(screen.getByText("欢迎")).toBeTruthy();
  });

  it("renders assistant with tool calls and markdown", () => {
    render(
      <MessageBubble
        m={{
          role: "assistant",
          content: "**结论**",
          tool_calls: [{ name: "search_code", input: { q: "x" }, ok: true }],
        }}
      />,
    );
    expect(screen.getByText("search_code")).toBeTruthy();
    expect(screen.getByText("结论")).toBeTruthy();
  });

  it("shows thinking placeholder when assistant content empty", () => {
    render(<MessageBubble m={{ role: "assistant", content: "" }} />);
    expect(screen.getByText("思考中…")).toBeTruthy();
  });
});

describe("ToolCallChip", () => {
  it("toggles input detail on click", () => {
    render(<ToolCallChip tc={{ name: "query_user", input: { user_id: "U1" }, ok: false }} />);
    expect(screen.queryByText(/user_id/)).toBeNull();
    fireEvent.click(screen.getByText("query_user"));
    expect(screen.getByText(/user_id/)).toBeTruthy();
  });
});

describe("TicketCard", () => {
  it("shows resolve buttons when resolved and fires callbacks", () => {
    const onConfirm = vi.fn();
    const onReject = vi.fn();
    render(
      <TicketCard
        externalId="AI-1"
        summary="卡片被锁"
        status="resolved"
        onConfirm={onConfirm}
        onReject={onReject}
      />,
    );
    fireEvent.click(screen.getByText("已解决"));
    expect(onConfirm).toHaveBeenCalled();
    fireEvent.click(screen.getByText("未解决"));
    expect(onReject).toHaveBeenCalled();
  });

  it("renders status label without buttons when pending", () => {
    render(<TicketCard externalId="AI-2" summary="问题" status="pending" />);
    expect(screen.getByText("等待受理")).toBeTruthy();
    expect(screen.queryByText("已解决")).toBeNull();
  });
});

describe("HandoffPrompt", () => {
  it("fires onClick", () => {
    const onClick = vi.fn();
    render(<HandoffPrompt onClick={onClick} disabled={false} />);
    fireEvent.click(screen.getByText("没解决？转人工 →"));
    expect(onClick).toHaveBeenCalled();
  });
});
