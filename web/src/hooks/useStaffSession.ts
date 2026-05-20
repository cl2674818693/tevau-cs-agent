import { useState } from "react";

const KEY = "staff_jwt";

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

  return { token, login, logout };
}
