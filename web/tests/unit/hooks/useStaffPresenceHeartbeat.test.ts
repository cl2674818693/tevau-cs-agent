// useStaffPresenceHeartbeat：mount 即送一次 + 每 300s 一次；token 失效后停。
import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as presence from "@/api/staffPresence";
import { STAFF_TOKEN_KEY } from "@/hooks/useStaffSession";
import { useStaffPresenceHeartbeat } from "@/hooks/useStaffPresenceHeartbeat";

import { clearLocalStorage } from "../../_helpers/storage";

describe("useStaffPresenceHeartbeat", () => {
  beforeEach(() => {
    clearLocalStorage();
    vi.useFakeTimers();
    vi.spyOn(presence, "sendHeartbeat").mockResolvedValue();
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("无 token 不发心跳", () => {
    renderHook(() => useStaffPresenceHeartbeat());
    expect(presence.sendHeartbeat).not.toHaveBeenCalled();
  });

  it("有 token：mount 立即发一次 + 每 300s 重复", () => {
    localStorage.setItem(STAFF_TOKEN_KEY, "tk");
    renderHook(() => useStaffPresenceHeartbeat());
    expect(presence.sendHeartbeat).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(300_000);
    expect(presence.sendHeartbeat).toHaveBeenCalledTimes(2);
    vi.advanceTimersByTime(300_000);
    expect(presence.sendHeartbeat).toHaveBeenCalledTimes(3);
  });

  it("卸载后停止心跳", () => {
    localStorage.setItem(STAFF_TOKEN_KEY, "tk");
    const { unmount } = renderHook(() => useStaffPresenceHeartbeat());
    expect(presence.sendHeartbeat).toHaveBeenCalledTimes(1);
    unmount();
    vi.advanceTimersByTime(300_000);
    expect(presence.sendHeartbeat).toHaveBeenCalledTimes(1);
  });

  it("心跳失败时静默吞错（不影响下一次）", async () => {
    (presence.sendHeartbeat as ReturnType<typeof vi.fn>).mockRejectedValue(new Error("net"));
    localStorage.setItem(STAFF_TOKEN_KEY, "tk");
    renderHook(() => useStaffPresenceHeartbeat());
    // 跑掉 pending microtask
    await vi.advanceTimersByTimeAsync(0);
    vi.advanceTimersByTime(300_000);
    await vi.advanceTimersByTimeAsync(0);
    expect(presence.sendHeartbeat).toHaveBeenCalledTimes(2);
  });
});
