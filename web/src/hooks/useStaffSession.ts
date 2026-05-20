import { useState } from "react";

const KEY = "staff_jwt";

/** 从 JWT payload 取 role（仅用于前端 UI 显隐；权限以后端为准）。 */
function roleFromToken(token: string | null): string | null {
  if (!token) return null;
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return typeof payload.role === "string" ? payload.role : null;
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

  return { token, role: roleFromToken(token), login, logout };
}
