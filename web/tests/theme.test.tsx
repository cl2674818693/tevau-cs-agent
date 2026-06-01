import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, beforeAll, beforeEach, vi } from "vitest";
import { ThemeProvider } from "@/providers/ThemeProvider";
import { useTheme } from "@/hooks/useTheme";

describe("useTheme", () => {
  beforeAll(() => {
    // jsdom localStorage 不完整，stub 一个全功能实现
    const store = new Map<string, string>();
    vi.stubGlobal("localStorage", {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => void store.set(k, String(v)),
      removeItem: (k: string) => void store.delete(k),
      clear: () => store.clear(),
      get length() { return store.size; },
      key: (i: number) => Array.from(store.keys())[i] ?? null,
    });

    // jsdom matchMedia 不完整，stub 一个基础实现
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: (q: string) => ({
        matches: false,
        media: q,
        addEventListener: () => {},
        removeEventListener: () => {},
      }),
    });
  });

  beforeEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove("dark");
  });

  it("默认 system 模式", () => {
    const { result } = renderHook(() => useTheme(), {
      wrapper: ({ children }) => <ThemeProvider>{children}</ThemeProvider>,
    });
    expect(result.current.theme).toBe("system");
  });

  it("setTheme('dark') 写 localStorage 并加 html.dark", () => {
    const { result } = renderHook(() => useTheme(), {
      wrapper: ({ children }) => <ThemeProvider>{children}</ThemeProvider>,
    });
    act(() => result.current.setTheme("dark"));
    expect(localStorage.getItem("theme")).toBe("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("setTheme('light') 移除 html.dark", () => {
    const { result } = renderHook(() => useTheme(), {
      wrapper: ({ children }) => <ThemeProvider>{children}</ThemeProvider>,
    });
    act(() => result.current.setTheme("dark"));
    act(() => result.current.setTheme("light"));
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });
});
