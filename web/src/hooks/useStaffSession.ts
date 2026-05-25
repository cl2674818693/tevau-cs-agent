import { useState } from "react";

const KEY = "staff_jwt";

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
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(KEY));

  function login(t: string) {
    localStorage.setItem(KEY, t);
    setToken(t);
  }

  function logout() {
    localStorage.removeItem(KEY);
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
