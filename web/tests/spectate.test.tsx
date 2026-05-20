import { render, renderHook, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { streamSpectateEvents, type StaffStreamEvent } from "../src/api/staff";
import { useStaffSession } from "../src/hooks/useStaffSession";

beforeEach(() => {
  const store = new Map<string, string>();
  vi.stubGlobal("localStorage", {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
    removeItem: (k: string) => void store.delete(k),
    clear: () => store.clear(),
  });
});
afterEach(() => vi.restoreAllMocks());

function fakeJwt(role: string): string {
  return `h.${btoa(JSON.stringify({ role, sub: "S1" }))}.s`;
}

function sseResponse(frames: string[]): Response {
  const body = new ReadableStream<Uint8Array>({
    start(c) {
      const enc = new TextEncoder();
      for (const f of frames) c.enqueue(enc.encode(f));
      c.close();
    },
  });
  return new Response(body, { status: 200 });
}

describe("useStaffSession role", () => {
  it("decodes role from jwt", () => {
    localStorage.setItem("staff_jwt", fakeJwt("senior"));
    const { result } = renderHook(() => useStaffSession());
    expect(result.current.role).toBe("senior");
  });

  it("null role when no token", () => {
    const { result } = renderHook(() => useStaffSession());
    expect(result.current.role).toBeNull();
  });
});

describe("streamSpectateEvents", () => {
  it("hits the spectate endpoint and yields events", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url: string) =>
        sseResponse([
          'event: assistant_text\ndata: {"content":"AI 说话"}\n\n',
          'event: tool_call\ndata: {"name":"query_user"}\n\n',
        ]),
      ),
    );
    const out: StaffStreamEvent[] = [];
    for await (const ev of streamSpectateEvents("t", 7)) out.push(ev);
    const url = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(url).toBe("/staff/api/v1/conversations/7/spectate-stream");
    expect(out[0]).toMatchObject({ type: "assistant_text", content: "AI 说话" });
  });
});

describe("SpectateRoute", () => {
  it("renders streamed events read-only", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        sseResponse([
          'event: user_message\ndata: {"content":"我卡被锁了"}\n\n',
          'event: assistant_text\ndata: {"content":"正在为您查询"}\n\n',
        ]),
      ),
    );
    localStorage.setItem("staff_jwt", fakeJwt("senior"));
    const { SpectateRoute } = await import("../src/routes/staff/SpectateRoute");
    render(
      <MemoryRouter initialEntries={["/staff/conversations/3/spectate"]}>
        <Routes>
          <Route path="/staff/conversations/:id/spectate" element={<SpectateRoute />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("AI：正在为您查询")).toBeTruthy());
    expect(screen.getByText("用户：我卡被锁了")).toBeTruthy();
  });
});
