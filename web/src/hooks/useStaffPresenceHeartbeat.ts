import { useEffect } from "react";

import { sendHeartbeat } from "../api/staffPresence";

import { useStaffSession } from "./useStaffSession";

const INTERVAL_MS = 60_000;

/** 客服已登录时定时发送在线心跳；登出后停止。 */
export function useStaffPresenceHeartbeat(): void {
  const { token } = useStaffSession();
  useEffect(() => {
    if (!token) return;
    sendHeartbeat(token).catch(() => {});
    const id = window.setInterval(() => {
      sendHeartbeat(token).catch(() => {});
    }, INTERVAL_MS);
    return () => {
      window.clearInterval(id);
    };
  }, [token]);
}
