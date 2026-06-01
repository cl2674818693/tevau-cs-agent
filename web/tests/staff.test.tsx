import { act, fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  listStaffConversations,
  sendStaffMessage,
  staffLogin,
  streamStaffEvents,
  takeConversation,
} from "../src/api/staff";
import { useStaffSession } from "../src/hooks/useStaffSession";
import { ConversationDetailRoute } from "../src/routes/staff/ConversationDetailRoute";
import { ConversationsListRoute } from "../src/routes/staff/ConversationsListRoute";
import { StaffLoginRoute } from "../src/routes/staff/StaffLoginRoute";

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

describe("useStaffSession", () => {
  it("login/logout persists token", () => {
    const { result } = renderHook(() => useStaffSession());
    expect(result.current.token).toBeNull();
    act(() => result.current.login("tok"));
    expect(result.current.token).toBe("tok");
    expect(localStorage.getItem("staff_jwt")).toBe("tok");
    act(() => result.current.logout());
    expect(result.current.token).toBeNull();
  });
});

describe("api/staff", () => {
  it("staffLogin returns token", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ token: "t", staff: {} }), { status: 200 })),
    );
    const out = await staffLogin("S100", "pw");
    expect(out.token).toBe("t");
  });

  it("takeConversation true on 200, false on 409", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(null, { status: 200 })),
    );
    expect(await takeConversation("t", 1)).toBe(true);
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(null, { status: 409 })),
    );
    expect(await takeConversation("t", 1)).toBe(false);
  });

  it("listStaffConversations returns items", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify([{ id: 1 }]), { status: 200 })),
    );
    const items = await listStaffConversations("t", "all");
    expect(items).toHaveLength(1);
  });

  it("sendStaffMessage posts content", async () => {
    const f = vi.fn(
      async (_url: string, _opts?: RequestInit) => new Response(null, { status: 200 }),
    );
    vi.stubGlobal("fetch", f);
    await sendStaffMessage("t", 1, "你好");
    expect((f.mock.calls[0][1] as RequestInit).body).toContain("你好");
  });

  it("streamStaffEvents parses frames", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => sseResponse(['event: human_message\ndata: {"content":"hi"}\n\n'])),
    );
    const evs = [];
    for await (const ev of streamStaffEvents("t", 1)) evs.push(ev);
    expect(evs[0]).toMatchObject({ type: "human_message", content: "hi" });
  });
});

describe("StaffLoginRoute", () => {
  it("logs in and navigates", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ token: "t", staff: {} }), { status: 200 })),
    );
    const { container } = render(
      <MemoryRouter>
        <StaffLoginRoute />
      </MemoryRouter>,
    );
    fireEvent.change(screen.getByPlaceholderText("工号"), { target: { value: "S100" } });
    fireEvent.change(screen.getByPlaceholderText("密码"), { target: { value: "pw" } });
    // antd Button 文本被 span 包裹，用 form.submit 触发 onFinish 更稳
    fireEvent.submit(container.querySelector("form")!);
    await waitFor(() => expect(localStorage.getItem("staff_jwt")).toBe("t"));
  });
});

describe("ConversationsListRoute", () => {
  it("renders conversations", async () => {
    localStorage.setItem("staff_jwt", "t");
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify([
              {
                id: 9,
                user_type: "c",
                subject_id: "U1",
                mode: "human_pending",
                assigned_staff_id: null,
                created_at: "",
              },
            ]),
            { status: 200 },
          ),
      ),
    );
    render(
      <MemoryRouter>
        <ConversationsListRoute />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText(/#9/)).toBeTruthy());
  });
});

describe("ConversationDetailRoute", () => {
  it("take then send", async () => {
    localStorage.setItem("staff_jwt", "t");
    const f = vi.fn(async (url: string) => {
      if (url.endsWith("/stream")) return sseResponse([]);
      return new Response(null, { status: 200 });
    });
    vi.stubGlobal("fetch", f);
    render(
      <MemoryRouter initialEntries={["/staff/conversations/5"]}>
        <Routes>
          <Route path="/staff/conversations/:id" element={<ConversationDetailRoute />} />
        </Routes>
      </MemoryRouter>,
    );
    // antd Button 在 jsdom 下文本不进入可访问 name，按 css 类定位"接管"按钮
    // （路由头部唯一一个 .ant-btn-primary）。TakeoverFooter 仍是 shadcn Button，
    // 其"发送"是普通 DOM text，可走 getByText。
    const container = document.body;
    await waitFor(() => {
      const btn = container.querySelector(".ant-btn-primary");
      if (!btn) throw new Error("take button not mounted");
    });
    fireEvent.click(container.querySelector(".ant-btn-primary")!);
    await waitFor(() => expect(screen.getByText("已接管")).toBeTruthy());
    const input = screen.getByPlaceholderText("回复用户…");
    fireEvent.change(input, { target: { value: "您好" } });
    fireEvent.click(screen.getByText("发送"));
    // 不再本地乐观回显（避免与 SSE 回推重复）：验证发送 API 被调用 + 输入框清空，
    // 消息显示交由会话事件流（/stream）统一驱动。
    await waitFor(() =>
      expect(
        f.mock.calls.some(([u]) => typeof u === "string" && u.endsWith("/conversations/5/messages")),
      ).toBe(true),
    );
    expect((input as HTMLInputElement).value).toBe("");
  });
});
