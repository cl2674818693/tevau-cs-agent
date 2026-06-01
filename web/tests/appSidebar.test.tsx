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
    expect(screen.getByText("数据大盘")).toBeInTheDocument();
    fireEvent.click(screen.getByText("运营看板"));
    // Radix Collapsible removes content from DOM when closed in jsdom (no animation)
    expect(screen.queryByText("数据大盘")).not.toBeInTheDocument();
  });
});
