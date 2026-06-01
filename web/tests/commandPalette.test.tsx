import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi, beforeAll } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { CommandPalette } from "@/components/app-shell/CommandPalette";

vi.mock("@/hooks/useStaffSession", () => ({
  useStaffSession: () => ({ role: "admin" }),
}));
vi.mock("@/hooks/useDynamicMenu", () => ({ useDynamicMenu: () => ({ matrix: null }) }));

beforeAll(() => {
  // jsdom 缺 ResizeObserver / scrollIntoView，cmdk 内部会用
  (globalThis as unknown as Record<string, unknown>).ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
  Element.prototype.scrollIntoView = vi.fn();
});

describe("CommandPalette", () => {
  it("⌘K 打开面板", () => {
    render(
      <MemoryRouter>
        <CommandPalette />
      </MemoryRouter>,
    );
    fireEvent.keyDown(window, { key: "k", metaKey: true });
    expect(screen.getByPlaceholderText(/搜索菜单/)).toBeInTheDocument();
  });
});
