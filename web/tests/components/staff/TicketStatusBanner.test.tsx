// TicketStatusBanner：顶部条，显示最新工单事件中文文案 + external_id。
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TicketStatusBanner } from "@/components/TicketStatusBanner";

describe("TicketStatusBanner", () => {
  it("空数组：不渲染", () => {
    const { container } = render(<TicketStatusBanner events={[]} />);
    expect(container.textContent).toBe("");
  });

  it("展示最新事件中文文案 + external_id", () => {
    render(
      <TicketStatusBanner
        events={[
          { event: "assigned", external_id: "T-1" },
          { event: "resolved", external_id: "T-1" },
        ]}
      />,
    );
    expect(screen.getByText(/工单已解决/)).toBeInTheDocument();
    expect(screen.getByText(/T-1/)).toBeInTheDocument();
  });

  it("未知事件 key 走原 event 名", () => {
    render(<TicketStatusBanner events={[{ event: "weird", external_id: "T-9" }]} />);
    expect(screen.getByText(/weird/)).toBeInTheDocument();
  });

  it("缺 external_id 时不带' · '后缀", () => {
    render(<TicketStatusBanner events={[{ event: "in_progress" }]} />);
    expect(screen.getByText(/工单处理中/)).toBeInTheDocument();
    // 不应出现 · 紧随其后（弱断言）
    expect(screen.queryByText(/·/)).toBeNull();
  });
});
