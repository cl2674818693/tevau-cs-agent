// ConversationDetailRoute（重点）：IM 气泡 + 右侧 SubjectInfoCard + 接管/释放/草稿。
// 测试矩阵（覆盖最近改动）：
//  1) 默认加载：会话信息拉取成功 + 历史消息渲染为 IM 气泡
//  2) 历史接口失败：仍不崩，SSE 增量仍可渲染
//  3) 接管按钮（未接管）：点击调 /take，UI 切「释放回 AI」
//  4) 接管被抢占（false）：显示 notice "已被其他客服接管" 并 refetch
//  5) 释放：点击调 /release，回到「接管」按钮
//  6) 他人已接管：按钮禁用 + 显示 "已被 X 接管" + 提示横幅
//  7) SubjectInfoCard 渲染：拉取 subject-info 成功 → 显示用户信息块
//  8) SubjectInfoCard 失败：仍不崩、不挡对话
//  9) 非法 conv id（NaN）→ 仍渲染面包屑/不崩
// 10) AI 草稿模式开关：开 → 调 /ai-draft/enable
// 11) SSE mode_change → InfoCard 旁的接管态同步（assigned_staff_id 更新）

import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// 把右上角 InfoCard 联动 SSE 的状态做端到端验证需要 mock streamStaffEvents 与 streamSpectateEvents
// 既然代码里直接从 api/staff 导出，我们用 vi.doMock 拦它的两个 generator + 让其它函数走真实路径

// streamStaffEvents 是 async generator；用 vi.hoisted 把可控推送器提到 mock 之前
const { stream } = vi.hoisted(() => {
  const s = {
    queue: [] as { value?: unknown; done?: boolean }[],
    waiters: [] as ((v: { value?: unknown; done?: boolean }) => void)[],
    push(ev: unknown) {
      if (this.waiters.length) {
        const w = this.waiters.shift()!;
        w({ value: ev });
      } else {
        this.queue.push({ value: ev });
      }
    },
    close() {
      if (this.waiters.length) {
        this.waiters.shift()!({ done: true });
      } else {
        this.queue.push({ done: true });
      }
    },
    next(): Promise<{ value?: unknown; done?: boolean }> {
      if (this.queue.length) return Promise.resolve(this.queue.shift()!);
      return new Promise((resolve) => this.waiters.push(resolve));
    },
    reset() {
      this.queue = [];
      this.waiters = [];
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

import {
  installFetch,
  jsonResponse,
  mockFetch,
  resetFetch,
} from "../../helpers/fetchMock";
import { renderWithRouter } from "../../helpers/render";
import { loginAsStaff, logoutStaff } from "../../helpers/session";

import { ConversationDetailRoute } from "@/routes/staff/ConversationDetailRoute";

const CONV_ID = 42;

function setupConvFetches(opts: {
  conv?: {
    id: number;
    user_type: string;
    subject_id: string;
    mode: string;
    assigned_staff_id: string | null;
    created_at?: string;
  };
  convStatus?: number;
  messages?: { id: number; role: string; content: string; status: string; created_at: string; error_code: null; topic_verdict: null }[];
  messagesStatus?: number;
  subjectInfo?: unknown;
  subjectStatus?: number;
} = {}) {
  // get conversation：pathname 严格等于（不带子路径）
  mockFetch(
    "GET",
    (u) => u.pathname === `/staff/api/v1/conversations/${CONV_ID}`,
    () => {
      if (opts.convStatus && opts.convStatus !== 200)
        return new Response("", { status: opts.convStatus });
      return jsonResponse(
        opts.conv ?? {
          id: CONV_ID,
          user_type: "c",
          subject_id: "u_alpha",
          mode: "human_pending",
          assigned_staff_id: null,
          created_at: "2026-01-01 00:00:00",
        },
      );
    },
  );
  mockFetch("GET", `/staff/api/v1/conversations/${CONV_ID}/messages`, () => {
    if (opts.messagesStatus && opts.messagesStatus !== 200)
      return new Response("", { status: opts.messagesStatus });
    return jsonResponse({
      messages: opts.messages ?? [],
      has_more: false,
    });
  });
  mockFetch("GET", `/staff/api/v1/conversations/${CONV_ID}/subject-info`, () => {
    if (opts.subjectStatus && opts.subjectStatus !== 200)
      return new Response("", { status: opts.subjectStatus });
    return jsonResponse(
      opts.subjectInfo ?? {
        subject: {
          user_type: "c",
          subject_id: "u_alpha",
          found: true,
          nick_name: "Alpha 小白",
          user_code: "UC123",
          email: "a@b.com",
          phone: "13800000000",
          user_status: "正常",
          kyc_status: "已认证",
          open_card_status: "已开卡",
          registration_time: "2025-01-01 00:00:00",
          last_login_time: "2026-01-01 00:00:00",
          recent_30d_transactions: [{ currency: "USD", count: 3, amount: "120.00" }],
        },
        client_info: {
          platform: "iOS",
          app_version: "1.2.3",
          user_agent: "TevauApp/1.2.3",
          updated_at: "2026-01-01 00:00:00",
        },
      },
    );
  });
}

describe("ConversationDetailRoute", () => {
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

  it("默认加载：面包屑 + 接管按钮 + 历史消息气泡渲染", async () => {
    setupConvFetches({
      messages: [
        { id: 1, role: "user", content: "我卡被锁了", status: "ok", error_code: null, topic_verdict: null, created_at: "2026-01-01 00:00:00" },
        { id: 2, role: "assistant", content: "请提供卡号后四位", status: "ok", error_code: null, topic_verdict: null, created_at: "2026-01-01 00:00:01" },
      ],
    });
    renderWithRouter(<ConversationDetailRoute />, {
      initialPath: `/staff/conversations/${CONV_ID}`,
      path: "/staff/conversations/:id",
    });
    expect(await screen.findByText(`会话 #${CONV_ID}`)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /接.?管/ })).toBeInTheDocument();
    expect(await screen.findByText("我卡被锁了")).toBeInTheDocument();
    expect(await screen.findByText("请提供卡号后四位")).toBeInTheDocument();
  });

  it("历史接口失败时不崩，仍可渲染外壳", async () => {
    setupConvFetches({ messagesStatus: 500 });
    renderWithRouter(<ConversationDetailRoute />, {
      initialPath: `/staff/conversations/${CONV_ID}`,
      path: "/staff/conversations/:id",
    });
    expect(await screen.findByText(`会话 #${CONV_ID}`)).toBeInTheDocument();
    // 历史失败 + 空 events → 渲染暂无消息提示
    await waitFor(() =>
      expect(screen.getByText(/该会话暂无消息/)).toBeInTheDocument(),
    );
  });

  it("接管成功：调 /take 后按钮变为「释放回 AI」", async () => {
    setupConvFetches();
    const takeCalls: Request[] = [];
    mockFetch("POST", `/staff/api/v1/conversations/${CONV_ID}/take`, (req) => {
      takeCalls.push(req);
      return jsonResponse({ ok: true });
    });

    renderWithRouter(<ConversationDetailRoute />, {
      initialPath: `/staff/conversations/${CONV_ID}`,
      path: "/staff/conversations/:id",
    });
    fireEvent.click(await screen.findByRole("button", { name: /^接.?管$/ }));

    await waitFor(() => expect(takeCalls.length).toBe(1));
    expect(await screen.findByRole("button", { name: /释放回 AI/ })).toBeInTheDocument();
    expect(screen.getByText("已接管")).toBeInTheDocument();
  });

  it("接管被抢占（409）→ 提示 + 再次 refetch 会话信息", async () => {
    let getCount = 0;
    mockFetch("GET", (u) => u.pathname === `/staff/api/v1/conversations/${CONV_ID}`, () => {
      getCount += 1;
      // 第一次未接管；第二次返回他人接管
      return jsonResponse({
        id: CONV_ID,
        user_type: "c",
        subject_id: "u_alpha",
        mode: getCount === 1 ? "human_pending" : "human_takeover",
        assigned_staff_id: getCount === 1 ? null : "s_bob",
        created_at: "2026-01-01 00:00:00",
      });
    });
    mockFetch("GET", `/staff/api/v1/conversations/${CONV_ID}/messages`, () =>
      jsonResponse({ messages: [], has_more: false }),
    );
    mockFetch("GET", `/staff/api/v1/conversations/${CONV_ID}/subject-info`, () =>
      jsonResponse({
        subject: { user_type: "c", subject_id: "u_alpha", found: false },
        client_info: null,
      }),
    );
    mockFetch("POST", `/staff/api/v1/conversations/${CONV_ID}/take`, () =>
      new Response("", { status: 409 }),
    );

    renderWithRouter(<ConversationDetailRoute />, {
      initialPath: `/staff/conversations/${CONV_ID}`,
      path: "/staff/conversations/:id",
    });
    fireEvent.click(await screen.findByRole("button", { name: /^接.?管$/ }));

    expect(await screen.findByText("该会话已被其他客服接管")).toBeInTheDocument();
    // 第二次 GET 触发 refetch
    await waitFor(() => expect(getCount).toBeGreaterThanOrEqual(2));
    // 之后应显示「已被 s_bob 接管」按钮（disabled）
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /已被 s_bob 接管/ })).toBeDisabled(),
    );
  });

  it("释放：点击「释放回 AI」调 /release，按钮变回「接管」", async () => {
    setupConvFetches({
      conv: {
        id: CONV_ID,
        user_type: "c",
        subject_id: "u_alpha",
        mode: "human_takeover",
        assigned_staff_id: "s_alice",
        created_at: "2026-01-01 00:00:00",
      },
    });
    const releaseCalls: Request[] = [];
    mockFetch("POST", `/staff/api/v1/conversations/${CONV_ID}/release`, (req) => {
      releaseCalls.push(req);
      return jsonResponse({ ok: true });
    });
    // TakeoverFooter 拉转派候选；mock 一个空候选
    mockFetch("GET", "/staff/api/v1/transfer-candidates", () =>
      jsonResponse({ candidates: [] }),
    );

    renderWithRouter(<ConversationDetailRoute />, {
      initialPath: `/staff/conversations/${CONV_ID}`,
      path: "/staff/conversations/:id",
    });

    const releaseBtn = await screen.findByRole("button", { name: /释放回 AI/ });
    fireEvent.click(releaseBtn);
    await waitFor(() => expect(releaseCalls.length).toBe(1));
    expect(await screen.findByRole("button", { name: /^接.?管$/ })).toBeInTheDocument();
    expect(screen.getByText("已释放回 AI")).toBeInTheDocument();
  });

  it("他人已接管：按钮禁用 + 显示提示横幅", async () => {
    setupConvFetches({
      conv: {
        id: CONV_ID,
        user_type: "c",
        subject_id: "u_alpha",
        mode: "human_takeover",
        assigned_staff_id: "s_bob",
        created_at: "2026-01-01 00:00:00",
      },
    });

    renderWithRouter(<ConversationDetailRoute />, {
      initialPath: `/staff/conversations/${CONV_ID}`,
      path: "/staff/conversations/:id",
    });

    expect(
      await screen.findByRole("button", { name: /已被 s_bob 接管/ }),
    ).toBeDisabled();
    expect(
      await screen.findByText(/已被 s_bob 接管，你处于只读状态/),
    ).toBeInTheDocument();
  });

  it("SubjectInfoCard：拉取成功 → 显示用户信息块", async () => {
    setupConvFetches();
    renderWithRouter(<ConversationDetailRoute />, {
      initialPath: `/staff/conversations/${CONV_ID}`,
      path: "/staff/conversations/:id",
    });

    // antd Card title
    expect(await screen.findByText("用户信息")).toBeInTheDocument();
    expect(await screen.findByText("Alpha 小白")).toBeInTheDocument();
    expect(screen.getByText("UC123")).toBeInTheDocument();
    // client_info
    expect(screen.getByText("iOS")).toBeInTheDocument();
    expect(screen.getByText("1.2.3")).toBeInTheDocument();
    // 近 30 天交易
    expect(screen.getByText(/USD 3笔/)).toBeInTheDocument();
  });

  it("SubjectInfoCard：拉取失败 → 卡片显示「拉取用户信息失败」，不影响对话渲染", async () => {
    setupConvFetches({ subjectStatus: 500 });
    renderWithRouter(<ConversationDetailRoute />, {
      initialPath: `/staff/conversations/${CONV_ID}`,
      path: "/staff/conversations/:id",
    });
    expect(await screen.findByText("拉取用户信息失败")).toBeInTheDocument();
    // 主对话区仍可见（接管按钮）
    expect(screen.getByRole("button", { name: /^接.?管$/ })).toBeInTheDocument();
  });

  it("AI 草稿模式按钮：点击调 /ai-draft/enable，文案切换", async () => {
    setupConvFetches();
    const enableCalls: Request[] = [];
    mockFetch("POST", `/staff/api/v1/conversations/${CONV_ID}/ai-draft/enable`, (req) => {
      enableCalls.push(req);
      return jsonResponse({ ok: true });
    });

    renderWithRouter(<ConversationDetailRoute />, {
      initialPath: `/staff/conversations/${CONV_ID}`,
      path: "/staff/conversations/:id",
    });

    fireEvent.click(await screen.findByRole("button", { name: /AI 草稿模式/ }));
    await waitFor(() => expect(enableCalls.length).toBe(1));
    expect(await screen.findByRole("button", { name: /关闭草稿模式/ })).toBeInTheDocument();
  });

  it("SSE mode_change：他人接管事件让按钮立刻进入禁用「已被 X 接管」", async () => {
    setupConvFetches();
    renderWithRouter(<ConversationDetailRoute />, {
      initialPath: `/staff/conversations/${CONV_ID}`,
      path: "/staff/conversations/:id",
    });
    await screen.findByRole("button", { name: /^接.?管$/ });

    // 推一条 mode_change → human_takeover by_staff_id=s_bob
    stream.push({ type: "mode_change", to: "human_takeover", by_staff_id: "s_bob" });

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /已被 s_bob 接管/ })).toBeDisabled(),
    );
  });

  it("非法 conv id（NaN）：仍渲染面包屑、不抛白屏", async () => {
    // 用 "abc" 做 id → Number("abc") = NaN
    mockFetch("GET", (u) => u.pathname === "/staff/api/v1/conversations/NaN", () =>
      new Response("", { status: 400 }),
    );
    mockFetch("GET", "/staff/api/v1/conversations/NaN/messages", () =>
      new Response("", { status: 400 }),
    );
    mockFetch("GET", "/staff/api/v1/conversations/NaN/subject-info", () =>
      new Response("", { status: 400 }),
    );

    renderWithRouter(<ConversationDetailRoute />, {
      initialPath: "/staff/conversations/abc",
      path: "/staff/conversations/:id",
    });
    expect(await screen.findByText(/会话 #NaN/)).toBeInTheDocument();
  });

  it("user_message SSE 事件 → 渲染用户气泡", async () => {
    setupConvFetches({ messages: [] });
    renderWithRouter(<ConversationDetailRoute />, {
      initialPath: `/staff/conversations/${CONV_ID}`,
      path: "/staff/conversations/:id",
    });
    // 等首次拉取完成
    await screen.findByRole("button", { name: /^接.?管$/ });

    stream.push({ type: "user_message", content: "你好客服" });
    await waitFor(() => expect(screen.getByText("你好客服")).toBeInTheDocument());

    // user_message 是左侧用户气泡，旁边的「用户」标签也应该出现
    const bubble = screen.getByText("你好客服");
    // 在 antd Card title 中也有「对话」二字；仅断言用户气泡在 conv 区域
    expect(bubble.closest("div")?.textContent).toMatch(/你好客服/);
    const userLabel = within(bubble.parentElement!.parentElement as HTMLElement).getByText("用户");
    expect(userLabel).toBeInTheDocument();
  });
});
