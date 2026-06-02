// AI 草稿剧本：
//  1) 客服接管会话（mode=human_takeover）
//  2) 客服点「AI 草稿模式」→ POST /ai-draft/enable
//  3) SSE 推 ai_draft_ready → AiDraftPanel 显示草稿
//  4) 客服点「直接发出」→ POST /ai-draft/approve；面板隐藏
//  5) 第二份草稿到来 → 改写后发送 → POST /ai-draft/reject with rewrite

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

const CONV = 88;

function baseFetches() {
  mockFetch("GET", (u) => u.pathname === `/staff/api/v1/conversations/${CONV}`, () =>
    jsonResponse({
      id: CONV,
      user_type: "c",
      subject_id: "u",
      mode: "human_takeover",
      assigned_staff_id: "s_alice",
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

describe("integration: AI 草稿剧本", () => {
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

  it("开启草稿 → 收到草稿 → 直接发出 → 第二份草稿改写发送", async () => {
    baseFetches();
    const enableCalls: Request[] = [];
    mockFetch("POST", `/staff/api/v1/conversations/${CONV}/ai-draft/enable`, (req) => {
      enableCalls.push(req);
      return jsonResponse({ ok: true });
    });
    const approveCalls: Request[] = [];
    mockFetch("POST", `/staff/api/v1/conversations/${CONV}/ai-draft/approve`, (req) => {
      approveCalls.push(req);
      return jsonResponse({ ok: true });
    });
    const rejectCalls: Request[] = [];
    mockFetch("POST", `/staff/api/v1/conversations/${CONV}/ai-draft/reject`, async (req) => {
      rejectCalls.push(req);
      return jsonResponse({ ok: true });
    });

    renderWithRouter(<ConversationDetailRoute />, {
      initialPath: `/staff/conversations/${CONV}`,
      path: "/staff/conversations/:id",
    });

    // 1) 开启草稿模式
    fireEvent.click(await screen.findByRole("button", { name: /AI 草稿模式/ }));
    await waitFor(() => expect(enableCalls.length).toBe(1));
    expect(await screen.findByRole("button", { name: /关闭草稿模式/ })).toBeInTheDocument();

    // 2) SSE 推草稿就绪
    stream.push({ type: "ai_draft_ready", draft: "您好，我帮您处理" });
    expect(await screen.findByText("您好，我帮您处理")).toBeInTheDocument();

    // 3) 直接发出
    fireEvent.click(screen.getByRole("button", { name: /直接发出/ }));
    await waitFor(() => expect(approveCalls.length).toBe(1));
    // 面板应消失
    await waitFor(() => expect(screen.queryByText("您好，我帮您处理")).toBeNull());

    // 4) 第二份草稿来 → 改写 → 改写后发送
    stream.push({ type: "ai_draft_ready", draft: "草稿二" });
    expect(await screen.findByText("草稿二")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /^改.?写$/ }));
    const textarea = screen.getByDisplayValue("草稿二") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: "改写后的内容" } });
    fireEvent.click(screen.getByRole("button", { name: /改写后发送/ }));
    await waitFor(() => expect(rejectCalls.length).toBe(1));
    const body = JSON.parse(await rejectCalls[0].text());
    expect(body).toEqual({ rewrite: "改写后的内容" });
  });
});
