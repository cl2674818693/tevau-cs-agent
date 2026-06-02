// useKeyboardInset：监听 visualViewport.resize/scroll，返回 innerHeight - vv.height - vv.offsetTop。
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { useKeyboardInset } from "@/hooks/useVisualViewport";

type Listener = () => void;

describe("useKeyboardInset", () => {
  let listeners: { resize: Listener[]; scroll: Listener[] };
  let originalInnerHeight: number;
  let originalVv: VisualViewport | undefined;

  beforeEach(() => {
    listeners = { resize: [], scroll: [] };
    originalInnerHeight = window.innerHeight;
    originalVv = window.visualViewport ?? undefined;
    Object.defineProperty(window, "innerHeight", {
      configurable: true,
      value: 800,
    });
    Object.defineProperty(window, "visualViewport", {
      configurable: true,
      value: {
        height: 800,
        offsetTop: 0,
        addEventListener: (type: string, cb: Listener) => {
          (listeners as Record<string, Listener[]>)[type]?.push(cb);
        },
        removeEventListener: (type: string, cb: Listener) => {
          const arr = (listeners as Record<string, Listener[]>)[type];
          if (!arr) return;
          const i = arr.indexOf(cb);
          if (i !== -1) arr.splice(i, 1);
        },
      } as unknown as VisualViewport,
    });
  });

  afterEach(() => {
    Object.defineProperty(window, "innerHeight", { configurable: true, value: originalInnerHeight });
    Object.defineProperty(window, "visualViewport", { configurable: true, value: originalVv });
  });

  it("初始 inset = 0（vv.height = innerHeight）", () => {
    const { result } = renderHook(() => useKeyboardInset());
    expect(result.current).toBe(0);
  });

  it("键盘弹起：vv.height < innerHeight → inset 为差值", () => {
    const { result } = renderHook(() => useKeyboardInset());
    (window.visualViewport as unknown as { height: number }).height = 500;
    act(() => listeners.resize.forEach((cb) => cb()));
    expect(result.current).toBe(300);
  });

  it("vv.offsetTop 也会从 inset 中扣除", () => {
    const { result } = renderHook(() => useKeyboardInset());
    (window.visualViewport as unknown as { height: number; offsetTop: number }).height = 500;
    (window.visualViewport as unknown as { offsetTop: number }).offsetTop = 50;
    act(() => listeners.resize.forEach((cb) => cb()));
    expect(result.current).toBe(250);
  });

  it("inset 不为负", () => {
    const { result } = renderHook(() => useKeyboardInset());
    (window.visualViewport as unknown as { height: number }).height = 1000; // 比 innerHeight 还大
    act(() => listeners.resize.forEach((cb) => cb()));
    expect(result.current).toBe(0);
  });

  it("scroll 事件也会触发 update", () => {
    const { result } = renderHook(() => useKeyboardInset());
    (window.visualViewport as unknown as { height: number }).height = 600;
    act(() => listeners.scroll.forEach((cb) => cb()));
    expect(result.current).toBe(200);
  });

  it("无 visualViewport 时返回 0 且不挂监听", () => {
    Object.defineProperty(window, "visualViewport", { configurable: true, value: undefined });
    const { result } = renderHook(() => useKeyboardInset());
    expect(result.current).toBe(0);
  });

  it("卸载时摘掉 listener", () => {
    const { unmount } = renderHook(() => useKeyboardInset());
    expect(listeners.resize.length).toBeGreaterThan(0);
    unmount();
    expect(listeners.resize.length).toBe(0);
    expect(listeners.scroll.length).toBe(0);
  });
});
