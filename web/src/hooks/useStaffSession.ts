import { useState } from "react";

export const STAFF_TOKEN_KEY = "staff_jwt";

/** 清除本地客服 token（登出 / token 失效时复用，避免散落 localStorage key）。 */
export function clearStaffToken() {
  localStorage.removeItem(STAFF_TOKEN_KEY);
}

/** 从 JWT payload 取一个 string 字段（仅用于前端 UI；权限以后端为准）。
 *  JWT 用 base64url 编码，atob 是 base64：- → + / _ → /，并补齐 padding；
 *  否则含 - 或 _ 的 payload 会抛 InvalidCharacterError 静默返回 null，
 *  staffId 拿不到 → 比较 assigned_staff_id 误判"他人接管"。 */
function claimFromToken(token: string | null, key: string): string | null {
  if (!token) return null;
  try {
    let seg = token.split(".")[1];
    if (!seg) return null;
    seg = seg.replace(/-/g, "+").replace(/_/g, "/");
    const pad = seg.length % 4;
    if (pad === 2) seg += "==";
    else if (pad === 3) seg += "=";
    else if (pad !== 0) return null;
    const payload = JSON.parse(atob(seg));
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
