// 转人工全链路（客服侧视角）：
//  1) 详情页订阅 SSE，初始 mode=ai
//  2) 后端推 request_human → 用户已请求人工（EventBubble center chip）
//  3) 客服点接管 → POST /take，UI 切「释放回 AI」+ TakeoverFooter 出现
//  4) 客服发送消息 → POST /messages with body { content, attachment_ids: [] }
//  5) 客服点「标记已解决」→ POST /resolve

import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { stream } = vi.hoisted(() => {
  const s = {
    q: [] as { value?: unknown; done?: boolean }[],
    waiters: [] as ((v: { value?: unknown; done?: boolean }) => void)[],
    push(ev: unknown) {
      if (this.waiters.length) this.waiters.shift()!({ value: ev });
      else this.q.push({ value: ev });
    },
    close() {
      const ws = this.waiters.splice(0);
      ws.forEach((w) => w({ done: true }));
    },
    reset() {
      this.q = [];
      this.waiters = [];
    },
    next(): Promise<{ value?: unknown; done?: boolean }> {
      if (this.q.length) return Promise.resolve(this.q.shift()!);
      return new Promise((r) => this.waiters.push(r));
    },
  };
  return { stream: s };
});
vi.mock("@/api/staff", async () => {
  const actual = await vi.importActual<typeof import("@/api/staff")>("@/api/staff");
  return {
    ...actual,
    streamStaffEvents: async function* () {
      for (;;) {
        const { value, done } = await stream.next();
        if (done) return;
        yield value as never;
      }
    },
  };
});

import { ConversationDetailRoute } from "@/routes/staff/ConversationDetailRoute";

import {
  installFetch,
  jsonResponse,
  mockFetch,
  resetFetch,
} from "../helpers/fetchMock";
import { renderWithRouter } from "../helpers/render";
import { loginAsStaff, logoutStaff } from "../helpers/session";

const CONV = 70;

function baseFetches(initialMode: string) {
  mockFetch("GET", (u) => u.pathname === `/staff/api/v1/conversations/${CONV}`, () =>
    jsonResponse({
      id: CONV,
      user_type: "c",
      subject_id: "u",
      mode: initialMode,
      assigned_staff_id: initialMode === "human_takeover" ? "s_alice" : null,
      created_at: "2026-01-01 00:00:00",
    }),
  );
  mockFetch("GET", `/staff/api/v1/conversations/${CONV}/messages`, () =>
    jsonResponse({ messages: [], has_more: false }),
  );
  mockFetch("GET", `/staff/api/v1/conversations/${CONV}/subject-info`, () =>
    jsonResponse({
      subject: { user_type: "c", subject_id: "u", found: false },
      client_info: null,
    }),
  );
  mockFetch("GET", "/staff/api/v1/transfer-candidates", () =>
    jsonResponse({ candidates: [] }),
  );
}

describe("integration: handoff 全链路（客服侧）", () => {
  beforeEach(() => {
    installFetch();
    loginAsStaff("s_alice", "agent");
    stream.reset();
  });
  afterEach(() => {
    stream.close();
    resetFetch();
    logoutStaff();
    stream.reset();
    vi.restoreAllMocks();
  });

  it("用户 request_human → 接管 → 发送消息 → 标记已解决", async () => {
    baseFetches("human_pending");
    const takeCalls: Request[] = [];
    mockFetch("POST", `/staff/api/v1/conversations/${CONV}/take`, (req) => {
      takeCalls.push(req);
      return jsonResponse({ ok: true });
    });
    const msgCalls: Request[] = [];
    mockFetch("POST", `/staff/api/v1/conversations/${CONV}/messages`, async (req) => {
      msgCalls.push(req);
      return jsonResponse({ ok: true });
    });
    const resolveCalls: Request[] = [];
    mockFetch("POST", `/staff/api/v1/conversations/${CONV}/resolve`, (req) => {
      resolveCalls.push(req);
      return jsonResponse({ ok: true });
    });

    renderWithRouter(<ConversationDetailRoute />, {
      initialPath: `/staff/conversations/${CONV}`,
      path: "/staff/conversations/:id",
    });

    // 1) SSE 推 request_human → 中心 chip
    stream.push({ type: "request_human" });
    expect(await screen.findByText("用户已请求人工")).toBeInTheDocument();

    // 2) 接管
    fireEvent.click(await screen.findByRole("button", { name: /^接.?管$/ }));
    await waitFor(() => expect(takeCalls.length).toBe(1));
    expect(await screen.findByRole("button", { name: /释放回 AI/ })).toBeInTheDocument();

    // 3) TakeoverFooter 出现：发送消息
    const input = await screen.findByPlaceholderText("回复用户…");
    fireEvent.change(input, { target: { value: "我帮你看下" } });
    fireEvent.click(screen.getByRole("button", { name: /^发.?送$/ }));
    await waitFor(() => expect(msgCalls.length).toBe(1));
    const body = JSON.parse(await msgCalls[0].text());
    expect(body).toEqual({ content: "我帮你看下", attachment_ids: [] });

    // 4) 标记已解决
    fireEvent.click(screen.getByRole("button", { name: /标记已解决/ }));
    await waitFor(() => expect(resolveCalls.length).toBe(1));
    expect(await screen.findByText(/已标记解决并释放回 AI/)).toBeInTheDocument();
  });

  it("接管失败 (409) → 提示 + 拒绝进入接管态", async () => {
    baseFetches("human_pending");
    mockFetch("POST", `/staff/api/v1/conversations/${CONV}/take`, () =>
      new Response("", { status: 409 }),
    );
    renderWithRouter(<ConversationDetailRoute />, {
      initialPath: `/staff/conversations/${CONV}`,
      path: "/staff/conversations/:id",
    });
    fireEvent.click(await screen.findByRole("button", { name: /^接.?管$/ }));
    expect(await screen.findByText(/该会话已被其他客服接管/)).toBeInTheDocument();
    // 按钮不应变成「释放回 AI」
    expect(screen.queryByRole("button", { name: /释放回 AI/ })).toBeNull();
  });

  it("SSE 后到的 mode_change → ai：assigned 清空，按钮回归「接管」", async () => {
    baseFetches("human_takeover");
    mockFetch("POST", `/staff/api/v1/conversations/${CONV}/take`, () =>
      jsonResponse({ ok: true }),
    );
    renderWithRouter(<ConversationDetailRoute />, {
      initialPath: `/staff/conversations/${CONV}`,
      path: "/staff/conversations/:id",
    });
    expect(await screen.findByRole("button", { name: /释放回 AI/ })).toBeInTheDocument();
    // 后端推 ai → 客服按钮应回「接管」
    stream.push({ type: "mode_change", to: "ai" });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /^接.?管$/ })).toBeInTheDocument(),
    );
  });
});
