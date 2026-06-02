// useSidebarCollapsed 把折叠分组 id 写入 localStorage 持久化。
import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { useSidebarCollapsed } from "@/hooks/useSidebarCollapsed";

import { clearLocalStorage } from "../../_helpers/storage";

describe("useSidebarCollapsed", () => {
  beforeEach(clearLocalStorage);

  it("初始全部展开（无任何折叠记录）", () => {
    const { result } = renderHook(() => useSidebarCollapsed());
    expect(result.current.collapsed("workbench")).toBe(false);
  });

  it("toggle 切换折叠态", () => {
    const { result } = renderHook(() => useSidebarCollapsed());
    act(() => result.current.toggle("workbench"));
    expect(result.current.collapsed("workbench")).toBe(true);
    act(() => result.current.toggle("workbench"));
    expect(result.current.collapsed("workbench")).toBe(false);
  });

  it("写入 localStorage", () => {
    const { result } = renderHook(() => useSidebarCollapsed());
    act(() => result.current.toggle("ops"));
    expect(JSON.parse(localStorage.getItem("sidebar-collapsed") ?? "[]")).toContain("ops");
  });

  it("初始从 localStorage 读取", () => {
    localStorage.setItem("sidebar-collapsed", JSON.stringify(["people"]));
    const { result } = renderHook(() => useSidebarCollapsed());
    expect(result.current.collapsed("people")).toBe(true);
    expect(result.current.collapsed("workbench")).toBe(false);
  });

  it("localStorage 坏 JSON 时回退空集合（不抛）", () => {
    localStorage.setItem("sidebar-collapsed", "{not-json");
    const { result } = renderHook(() => useSidebarCollapsed());
    expect(result.current.collapsed("workbench")).toBe(false);
  });

  it("多分组独立 toggle", () => {
    const { result } = renderHook(() => useSidebarCollapsed());
    act(() => result.current.toggle("a"));
    act(() => result.current.toggle("b"));
    expect(result.current.collapsed("a")).toBe(true);
    expect(result.current.collapsed("b")).toBe(true);
    act(() => result.current.toggle("a"));
    expect(result.current.collapsed("a")).toBe(false);
    expect(result.current.collapsed("b")).toBe(true);
  });
});
