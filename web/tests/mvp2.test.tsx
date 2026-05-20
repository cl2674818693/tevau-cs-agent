import { act, fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { requestHuman, sendTicketUserEvent } from "../src/api/chat";
import { MessageBubble } from "../src/components/MessageBubble";
import { useAppBridge } from "../src/hooks/useAppBridge";
import { BuLoginRoute } from "../src/routes/BuLoginRoute";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("MessageBubble human_agent", () => {
  it("renders agent bubble with name", () => {
    render(
      <MessageBubble m={{ role: "human_agent", content: "已为您解锁", display_name: "张三" }} />,
    );
    expect(screen.getByText("已为您解锁")).toBeTruthy();
    expect(screen.getByText(/张三/)).toBeTruthy();
  });
});

describe("api helpers", () => {
  it("requestHuman posts to /request-human with X-BU-ID", async () => {
    const fetchMock = vi.fn(
      async (_url: string, _opts?: RequestInit) => new Response(null, { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await requestHuman(42, "BU1", "理由");
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v1/conversations/42/request-human");
    expect((opts as RequestInit).headers).toMatchObject({ "X-BU-ID": "BU1" });
  });

  it("sendTicketUserEvent posts the event", async () => {
    const fetchMock = vi.fn(
      async (_url: string, _opts?: RequestInit) => new Response(null, { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await sendTicketUserEvent("AI-1", "BU1", "user_confirmed_resolved");
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v1/tickets/AI-1/user-events");
    expect((opts as RequestInit).body).toContain("user_confirmed_resolved");
  });
});

describe("useAppBridge", () => {
  it("captures token injected by APP bridge", () => {
    const { result } = renderHook(() => useAppBridge());
    expect(result.current).toBeNull();
    act(() => window.aiEngineSetToken?.("jwt-abc"));
    expect(result.current).toBe("jwt-abc");
  });
});

describe("BuLoginRoute", () => {
  it("submits bu_id and navigates on success", async () => {
    const fetchMock = vi.fn(
      async (_url: string, _opts?: RequestInit) => new Response(null, { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(
      <MemoryRouter>
        <BuLoginRoute />
      </MemoryRouter>,
    );
    fireEvent.change(screen.getByPlaceholderText(/主账户 ID/), {
      target: { value: "BU00243780" },
    });
    fireEvent.click(screen.getByText("进入对话"));
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [url] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v1/auth/bu/login");
  });

  it("shows error text on failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async (_url: string, _opts?: RequestInit) =>
          new Response("主账户不存在或已禁用", { status: 401 }),
      ),
    );
    render(
      <MemoryRouter>
        <BuLoginRoute />
      </MemoryRouter>,
    );
    fireEvent.change(screen.getByPlaceholderText(/主账户 ID/), { target: { value: "BUx" } });
    fireEvent.click(screen.getByText("进入对话"));
    await waitFor(() => expect(screen.getByText(/不存在或已禁用/)).toBeTruthy());
  });
});
