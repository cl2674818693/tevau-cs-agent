import { render, screen, fireEvent } from "@testing-library/react";
import { App as AntdApp, ConfigProvider } from "antd";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { CommandPalette } from "@/components/app-shell/CommandPalette";

vi.mock("@/hooks/useStaffSession", () => ({
  useStaffSession: () => ({ role: "admin" }),
}));
vi.mock("@/hooks/useDynamicMenu", () => ({
  useDynamicMenu: () => ({ matrix: null }),
}));

describe("CommandPalette", () => {
  it("⌘K 打开面板", async () => {
    render(
      <ConfigProvider>
        <AntdApp>
          <MemoryRouter>
            <CommandPalette />
          </MemoryRouter>
        </AntdApp>
      </ConfigProvider>,
    );
    fireEvent.keyDown(window, { key: "k", metaKey: true });
    // antd v6 AutoComplete 的 placeholder 是独立 div，而非 input[placeholder] 属性，
    // 用 findByText 等 Modal Portal 渲染就绪后再断言。
    expect(await screen.findByText(/搜索菜单/)).toBeInTheDocument();
  });
});
