// useDynamicMenu：只在 admin 角色 + 有 token 时拉 matrix；403/其它角色静默 null。
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as rbacApi from "@/api/adminRbac";
import { STAFF_TOKEN_KEY } from "@/hooks/useStaffSession";
import { useDynamicMenu } from "@/hooks/useDynamicMenu";

import { clearLocalStorage } from "../../_helpers/storage";

function b64url(s: string): string {
  return btoa(s).replace(/=+$/, "").replace(/\+/g, "-").replace(/\//g, "_");
}
function makeJwt(payload: object): string {
  return `h.${b64url(JSON.stringify(payload))}.s`;
}

describe("useDynamicMenu", () => {
  beforeEach(() => {
    clearLocalStorage();
    vi.restoreAllMocks();
  });
  afterEach(() => vi.restoreAllMocks());

  it("无 token：loading=false / matrix=null / 不发请求", async () => {
    const spy = vi.spyOn(rbacApi, "getMatrix").mockResolvedValue({
      matrix: {},
      roles: [],
      permission_keys: [],
    });
    const { result } = renderHook(() => useDynamicMenu());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.matrix).toBeNull();
    expect(spy).not.toHaveBeenCalled();
  });

  it("非 admin 角色：不发请求 / matrix=null", async () => {
    localStorage.setItem(STAFF_TOKEN_KEY, makeJwt({ sub: "x", role: "agent" }));
    const spy = vi.spyOn(rbacApi, "getMatrix").mockResolvedValue({
      matrix: {},
      roles: [],
      permission_keys: [],
    });
    const { result } = renderHook(() => useDynamicMenu());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(spy).not.toHaveBeenCalled();
  });

  it("admin 角色：拉到 matrix", async () => {
    localStorage.setItem(STAFF_TOKEN_KEY, makeJwt({ sub: "x", role: "admin" }));
    const m = {
      matrix: { admin: { "admin.dashboard": true } },
      roles: ["admin"],
      permission_keys: ["admin.dashboard"],
    };
    vi.spyOn(rbacApi, "getMatrix").mockResolvedValue(m);
    const { result } = renderHook(() => useDynamicMenu());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.matrix).toEqual(m);
  });

  it("getMatrix 失败：静默 null（不抛）", async () => {
    localStorage.setItem(STAFF_TOKEN_KEY, makeJwt({ sub: "x", role: "admin" }));
    vi.spyOn(rbacApi, "getMatrix").mockRejectedValue(new Error("403"));
    const { result } = renderHook(() => useDynamicMenu());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.matrix).toBeNull();
  });
});
