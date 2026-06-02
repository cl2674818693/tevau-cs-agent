// TicketCard：工单卡片，resolved 时显示确认/拒绝按钮。
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TicketCard } from "@/components/TicketCard";

describe("TicketCard", () => {
  it("非 resolved 状态：不渲染按钮", () => {
    render(<TicketCard externalId="T-1" summary="处理中说明" status="in_progress" />);
    expect(screen.getByText("T-1")).toBeInTheDocument();
    expect(screen.getByText("处理中说明")).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("resolved 状态：渲染已解决 / 未解决按钮", () => {
    render(<TicketCard externalId="T-9" summary="x" status="resolved" />);
    expect(screen.getByRole("button", { name: /已解决/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /未解决/ })).toBeInTheDocument();
  });

  it("点击已解决/未解决回调", () => {
    const onC = vi.fn();
    const onR = vi.fn();
    render(<TicketCard externalId="T-9" summary="x" status="resolved" onConfirm={onC} onReject={onR} />);
    fireEvent.click(screen.getByRole("button", { name: /已解决/ }));
    expect(onC).toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: /未解决/ }));
    expect(onR).toHaveBeenCalled();
  });

  it("status 中文标签映射：pending → 等待受理", () => {
    render(<TicketCard externalId="T" summary="s" status="pending" />);
    expect(screen.getByText("等待受理")).toBeInTheDocument();
  });

  it("未知 status 走原值", () => {
    render(
      <TicketCard externalId="T" summary="s" status={"unknown" as "pending"} />,
    );
    expect(screen.getByText("unknown")).toBeInTheDocument();
  });
});
