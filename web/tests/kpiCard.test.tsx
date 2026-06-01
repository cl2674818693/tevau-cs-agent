import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { KpiCard } from "@/components/admin/KpiCard";

describe("KpiCard", () => {
  it("渲染 label / value / delta", () => {
    render(<KpiCard label="今日会话" value="1,234" delta="+12.3%" trend="up" />);
    expect(screen.getByText("今日会话")).toBeInTheDocument();
    expect(screen.getByText("1,234")).toBeInTheDocument();
    expect(screen.getByText("+12.3%")).toBeInTheDocument();
  });
});
