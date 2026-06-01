import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, beforeAll, beforeEach, vi } from "vitest";
import { useSidebarCollapsed } from "@/hooks/useSidebarCollapsed";

describe("useSidebarCollapsed", () => {
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

  beforeEach(() => localStorage.clear());

  it("默认全展开（无 localStorage）", () => {
    const { result } = renderHook(() => useSidebarCollapsed());
    expect(result.current.collapsed("workbench")).toBe(false);
  });

  it("toggle 写 localStorage", () => {
    const { result } = renderHook(() => useSidebarCollapsed());
    act(() => result.current.toggle("workbench"));
    expect(result.current.collapsed("workbench")).toBe(true);
    expect(localStorage.getItem("sidebar-collapsed")).toContain("workbench");
  });

  it("再次 toggle 还原", () => {
    const { result } = renderHook(() => useSidebarCollapsed());
    act(() => result.current.toggle("workbench"));
    act(() => result.current.toggle("workbench"));
    expect(result.current.collapsed("workbench")).toBe(false);
  });
});
