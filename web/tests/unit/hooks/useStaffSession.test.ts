// useStaffSession：token 持久化 + JWT claims 解析。
// JWT 用 base64url，含 - 或 _ 时旧实现会 atob 抛错；测确认现实现已修。
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { clearStaffToken, STAFF_TOKEN_KEY, useStaffSession } from "@/hooks/useStaffSession";

import { clearLocalStorage } from "../../_helpers/storage";

/** base64url 编码（不含 padding，含 -/_）。 */
function b64url(s: string): string {
  return btoa(s).replace(/=+$/, "").replace(/\+/g, "-").replace(/\//g, "_");
}

function makeJwt(payload: object): string {
  const header = b64url(JSON.stringify({ alg: "none", typ: "JWT" }));
  const body = b64url(JSON.stringify(payload));
  return `${header}.${body}.sig`;
}

describe("useStaffSession", () => {
  beforeEach(() => {
    clearLocalStorage();
  });
  afterEach(() => {
    clearLocalStorage();
  });

  it("初始无 token", () => {
    const { result } = renderHook(() => useStaffSession());
    expect(result.current.token).toBeNull();
    expect(result.current.role).toBeNull();
    expect(result.current.staffId).toBeNull();
  });

  it("从已有 localStorage 恢复 token", () => {
    const tk = makeJwt({ sub: "u1", role: "admin" });
    localStorage.setItem(STAFF_TOKEN_KEY, tk);
    const { result } = renderHook(() => useStaffSession());
    expect(result.current.token).toBe(tk);
    expect(result.current.role).toBe("admin");
    expect(result.current.staffId).toBe("u1");
  });

  it("login 写入 localStorage 并更新 state", () => {
    const { result } = renderHook(() => useStaffSession());
    const tk = makeJwt({ sub: "agent-9", role: "agent" });
    act(() => result.current.login(tk));
    expect(localStorage.getItem(STAFF_TOKEN_KEY)).toBe(tk);
    expect(result.current.token).toBe(tk);
    expect(result.current.role).toBe("agent");
  });

  it("logout 清 localStorage 并复位 state", () => {
    const tk = makeJwt({ sub: "u1", role: "admin" });
    localStorage.setItem(STAFF_TOKEN_KEY, tk);
    const { result } = renderHook(() => useStaffSession());
    act(() => result.current.logout());
    expect(localStorage.getItem(STAFF_TOKEN_KEY)).toBeNull();
    expect(result.current.token).toBeNull();
  });

  it("payload 含 -/_ 时仍能解析（修复点）", () => {
    // 让 payload 字节包含会被 base64 编码成 +/ 的字符，从而 b64url 后含 -/_
    // 一段随机字节可触发：byte 0xFB 0xEF → "+++" 在标 b64 / "---" 在 url。
    const payload = JSON.stringify({ sub: "user-" + "ûïÿ".repeat(3), role: "admin" });
    const header = b64url(JSON.stringify({ alg: "none" }));
    const body = b64url(payload);
    expect(body).toMatch(/[-_]/); // 确保确实有 - 或 _
    const tk = `${header}.${body}.sig`;
    localStorage.setItem(STAFF_TOKEN_KEY, tk);
    const { result } = renderHook(() => useStaffSession());
    expect(result.current.role).toBe("admin");
  });

  it("非 string 字段返回 null（防注入）", () => {
    const tk = makeJwt({ sub: 12345, role: { not: "string" } });
    localStorage.setItem(STAFF_TOKEN_KEY, tk);
    const { result } = renderHook(() => useStaffSession());
    expect(result.current.staffId).toBeNull();
    expect(result.current.role).toBeNull();
  });

  it("空 payload 段返回 null（不抛）", () => {
    localStorage.setItem(STAFF_TOKEN_KEY, "abc..sig");
    const { result } = renderHook(() => useStaffSession());
    expect(result.current.staffId).toBeNull();
  });

  it("非 JWT 形式 token 不抛错", () => {
    localStorage.setItem(STAFF_TOKEN_KEY, "garbage");
    const { result } = renderHook(() => useStaffSession());
    expect(result.current.role).toBeNull();
    expect(result.current.staffId).toBeNull();
  });

  it("clearStaffToken 单独可用（导出 helper）", () => {
    localStorage.setItem(STAFF_TOKEN_KEY, "x");
    clearStaffToken();
    expect(localStorage.getItem(STAFF_TOKEN_KEY)).toBeNull();
  });
});
