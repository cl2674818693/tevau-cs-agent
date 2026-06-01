import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, beforeAll } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { AppSidebar } from "@/components/app-shell/AppSidebar";

vi.mock("@/hooks/useStaffSession", () => ({
  useStaffSession: () => ({ role: "admin", token: "tk", logout: vi.fn() }),
}));
vi.mock("@/hooks/useDynamicMenu", () => ({ useDynamicMenu: () => ({ matrix: null }) }));

beforeAll(() => {
  const store = new Map<string, string>();
  vi.stubGlobal("localStorage", {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, String(v)),
    removeItem: (k: string) => void store.delete(k),
    clear: () => store.clear(),
    get length() { return store.size; },
    key: (i: number) => Array.from(store.keys())[i] ?? null,
  });
});

describe("AppSidebar", () => {
  beforeEach(() => localStorage.clear());

  it("admin 角色能看到 5 个分组", () => {
    render(
      <MemoryRouter>
        <AppSidebar />
      </MemoryRouter>,
    );
    expect(screen.getByText("工作台")).toBeInTheDocument();
    expect(screen.getByText("运营看板")).toBeInTheDocument();
    expect(screen.getByText("质检与审计")).toBeInTheDocument();
    expect(screen.getByText("AI 配置")).toBeInTheDocument();
    expect(screen.getByText("坐席与权限")).toBeInTheDocument();
  });

  it("点击分组标题折叠/展开", () => {
    render(
      <MemoryRouter>
        <AppSidebar />
      </MemoryRouter>,
    );
    // antd Menu inline mode 下，SubMenu 标题渲染为 role=button，aria-expanded 反映开合
    const groupTrigger = screen.getByText("运营看板").closest('[role="menuitem"]')!;
    expect(groupTrigger).toHaveAttribute("aria-expanded", "true");
    fireEvent.click(groupTrigger);
    expect(groupTrigger).toHaveAttribute("aria-expanded", "false");
  });
});
