import { useState } from "react";

export const STAFF_TOKEN_KEY = "staff_jwt";

/** 清除本地客服 token（登出 / token 失效时复用，避免散落 localStorage key）。 */
export function clearStaffToken() {
  localStorage.removeItem(STAFF_TOKEN_KEY);
}

/** 从 JWT payload 取一个 string 字段（仅用于前端 UI；权限以后端为准）。 */
function claimFromToken(token: string | null, key: string): string | null {
  if (!token) return null;
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return typeof payload[key] === "string" ? payload[key] : null;
  } catch {
    return null;
  }
}

export function useStaffSession() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(STAFF_TOKEN_KEY));

  function login(t: string) {
    localStorage.setItem(STAFF_TOKEN_KEY, t);
    setToken(t);
  }

  function logout() {
    clearStaffToken();
    setToken(null);
  }

  return {
    token,
    role: claimFromToken(token, "role"),
    staffId: claimFromToken(token, "sub"),
    login,
    logout,
  };
}
