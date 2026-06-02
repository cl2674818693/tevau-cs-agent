// MobileSidebar：汉堡按钮打开抽屉，抽屉内 AppSidebar 点击后 onClose。
import { App as AntApp } from "antd";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/api/staffFetch", () => ({ staffFetch: vi.fn() }));

import { MobileSidebar } from "@/components/app-shell/MobileSidebar";

function wrap(ui: React.ReactNode) {
  return render(
    <MemoryRouter>
      <AntApp>{ui}</AntApp>
    </MemoryRouter>,
  );
}

describe("MobileSidebar", () => {
  it("默认渲染汉堡按钮，抽屉关闭", () => {
    wrap(<MobileSidebar />);
    expect(screen.getByLabelText("打开菜单")).toBeInTheDocument();
    // 抽屉关闭时不渲染品牌名
    expect(screen.queryByText("Tevau 客服 AI 引擎")).toBeNull();
  });

  it("点击汉堡：抽屉打开，渲染 AppSidebar", async () => {
    wrap(<MobileSidebar />);
    fireEvent.click(screen.getByLabelText("打开菜单"));
    await waitFor(() =>
      expect(screen.getByText("Tevau 客服 AI 引擎")).toBeInTheDocument(),
    );
  });
});
