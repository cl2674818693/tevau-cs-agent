// MessageList：渲染多条 + onFeedback 回调透传 message index + scrollIntoView 容错。
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MessageList } from "@/components/MessageList";
import type { Message } from "@/types";

describe("MessageList", () => {
  it("空数组渲染 role=log 容器（无消息）", () => {
    render(<MessageList messages={[]} />);
    expect(screen.getByRole("log")).toBeInTheDocument();
  });

  it("渲染多条不同 role 的消息", () => {
    const msgs: Message[] = [
      { role: "system", content: "已连接" },
      { role: "user", content: "问题 1" },
      { role: "assistant", content: "回复 1" },
    ];
    render(<MessageList messages={msgs} />);
    expect(screen.getByText("已连接")).toBeInTheDocument();
    expect(screen.getByText("问题 1")).toBeInTheDocument();
    expect(screen.getByText("回复 1")).toBeInTheDocument();
  });

  it("onFeedback 仅对 assistant 行可用，回调带 message index", () => {
    const onFb = vi.fn();
    const msgs: Message[] = [
      { role: "system", content: "g" },
      { role: "user", content: "u" },
      { role: "assistant", content: "答案一" },
      { role: "assistant", content: "答案二" },
    ];
    render(<MessageList messages={msgs} onFeedback={onFb} />);
    const ups = screen.getAllByLabelText("有帮助");
    expect(ups).toHaveLength(2);
    fireEvent.click(ups[1]);
    expect(onFb).toHaveBeenCalledWith(3, "up");
  });

  it("aria-live=polite + role=log 满足无障碍", () => {
    render(<MessageList messages={[]} />);
    const log = screen.getByRole("log");
    expect(log).toHaveAttribute("aria-live", "polite");
  });

  it("messages 变更不抛错（即便 jsdom 无 scrollTo）", () => {
    const { rerender } = render(<MessageList messages={[]} />);
    rerender(
      <MessageList
        messages={[{ role: "system", content: "x" }]}
      />,
    );
    expect(screen.getByText("x")).toBeInTheDocument();
  });
});
