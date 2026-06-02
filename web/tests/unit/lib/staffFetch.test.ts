// staffFetch 在 401 时清掉 token + 跳登录页；其余透传。
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { staffFetch } from "@/api/staffFetch";
import { STAFF_TOKEN_KEY } from "@/hooks/useStaffSession";

describe("staffFetch", () => {
  // jsdom 默认 window.location.href 不可写，要重写一份 stub。
  let originalLocation: Location;
  let hrefSetter: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    // 沙箱 localStorage 缺 .clear()；按 key 删。
    const keys: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k) keys.push(k);
    }
    keys.forEach((k) => localStorage.removeItem(k));
    localStorage.setItem(STAFF_TOKEN_KEY, "tk-1");
    originalLocation = window.location;
    hrefSetter = vi.fn();
    // 用 defineProperty 把 location 替成可控对象
    Object.defineProperty(window, "location", {
      writable: true,
      value: {
        ...originalLocation,
        pathname: "/staff/conversations",
        get href() {
          return "current";
        },
        set href(v: string) {
          hrefSetter(v);
        },
      },
    });
    vi.spyOn(globalThis, "fetch");
  });

  afterEach(() => {
    Object.defineProperty(window, "location", {
      writable: true,
      value: originalLocation,
    });
    vi.restoreAllMocks();
  });

  it("非 401 透传响应、不动 token、不跳转", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue(
      new Response("{}", { status: 200 }),
    );
    const r = await staffFetch("/staff/api/v1/x");
    expect(r.status).toBe(200);
    expect(localStorage.getItem(STAFF_TOKEN_KEY)).toBe("tk-1");
    expect(hrefSetter).not.toHaveBeenCalled();
  });

  it("4xx（非 401）也不触发登出", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue(
      new Response("", { status: 403 }),
    );
    await staffFetch("/staff/api/v1/x");
    expect(localStorage.getItem(STAFF_TOKEN_KEY)).toBe("tk-1");
    expect(hrefSetter).not.toHaveBeenCalled();
  });

  it("401 时清 token 并硬跳 /staff/login", async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue(
      new Response("", { status: 401 }),
    );
    await staffFetch("/staff/api/v1/x");
    expect(localStorage.getItem(STAFF_TOKEN_KEY)).toBeNull();
    expect(hrefSetter).toHaveBeenCalledWith("/staff/login");
  });

  it("已在 /staff/login 时 401 不重复跳转（避免覆盖错误提示）", async () => {
    Object.defineProperty(window, "location", {
      writable: true,
      value: {
        ...originalLocation,
        pathname: "/staff/login",
        get href() {
          return "x";
        },
        set href(v: string) {
          hrefSetter(v);
        },
      },
    });
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue(
      new Response("", { status: 401 }),
    );
    await staffFetch("/staff/api/v1/auth/login");
    // 即使在登录页 staff token 仍会被清（幂等无副作用），但不能跳转。
    expect(hrefSetter).not.toHaveBeenCalled();
  });

  it("透传 init 参数（method/headers/body）", async () => {
    const spy = (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue(
      new Response("", { status: 200 }),
    );
    await staffFetch("/staff/api/v1/x", {
      method: "POST",
      headers: { "X-Custom": "1" },
      body: '{"a":1}',
    });
    expect(spy).toHaveBeenCalledWith("/staff/api/v1/x", {
      method: "POST",
      headers: { "X-Custom": "1" },
      body: '{"a":1}',
    });
  });
});
