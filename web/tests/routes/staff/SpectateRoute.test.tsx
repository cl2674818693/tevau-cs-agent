// SpectateRoute：旁观（senior/engineer）只读流。
// 用例覆盖：
//  1) 未登录 → 跳 /staff/login
//  2) SSE 流推 assistant_text / tool_use / mode_change → 条目正确渲染
//  3) SSE 失败 → 错误提示
//  4) 空状态 → "等待会话活动…"
//  5) 点击「返回工作台」→ 跳 /staff/conversations

import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { stream } = vi.hoisted(() => {
  const s = {
    q: [] as { value?: unknown; done?: boolean }[],
    waiters: [] as ((v: { value?: unknown; done?: boolean }) => void)[],
    fail: false as boolean | Error,
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
      this.fail = false;
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
    streamSpectateEvents: async function* () {
      if (stream.fail) {
        throw stream.fail instanceof Error ? stream.fail : new Error("spectate failed");
      }
      for (;;) {
        const { value, done } = await stream.next();
        if (done) return;
        yield value as never;
      }
    },
  };
});

import { SpectateRoute } from "@/routes/staff/SpectateRoute";

import { installFetch, resetFetch } from "../../helpers/fetchMock";
import { renderWithRouter } from "../../helpers/render";
import { loginAsStaff, logoutStaff } from "../../helpers/session";

describe("SpectateRoute", () => {
  beforeEach(() => {
    installFetch();
    stream.reset();
  });
  afterEach(() => {
    stream.close();
    resetFetch();
    logoutStaff();
    stream.reset();
    vi.restoreAllMocks();
  });

  it("未登录 → 跳 /staff/login", async () => {
    logoutStaff();
    renderWithRouter(<SpectateRoute />, {
      initialPath: "/staff/conversations/1/spectate",
      path: "/staff/conversations/:id/spectate",
      extraRoutes: [
        { path: "/staff/login", element: <div data-testid="login-stub">LOGIN</div> },
      ],
    });
    expect(await screen.findByTestId("login-stub")).toBeInTheDocument();
  });

  it("空数据：渲染「等待会话活动…」", async () => {
    loginAsStaff("s_alice", "senior");
    renderWithRouter(<SpectateRoute />, {
      initialPath: "/staff/conversations/1/spectate",
      path: "/staff/conversations/:id/spectate",
    });
    expect(await screen.findByText(/等待会话活动/)).toBeInTheDocument();
  });

  it("SSE 推 assistant_text / tool_use → 渲染对应文案", async () => {
    loginAsStaff("s_alice", "senior");
    renderWithRouter(<SpectateRoute />, {
      initialPath: "/staff/conversations/1/spectate",
      path: "/staff/conversations/:id/spectate",
    });
    await screen.findByText(/旁观 #1/);

    stream.push({ type: "assistant_text", content: "嗨，正在查您的订单" });
    stream.push({ type: "tool_use", name: "query_user", input: { id: 7 } });
    stream.push({ type: "tool_result", name: "query_user", ok: true, result_count: 1 });

    await waitFor(() => expect(screen.getByText(/AI：嗨/)).toBeInTheDocument());
    expect(screen.getByText(/调用工具：query_user/)).toBeInTheDocument();
    expect(screen.getByText(/工具返回：query_user（1 条）/)).toBeInTheDocument();
  });

  it("SSE 失败 → 错误提示", async () => {
    loginAsStaff("s_alice", "senior");
    stream.fail = true;
    renderWithRouter(<SpectateRoute />, {
      initialPath: "/staff/conversations/1/spectate",
      path: "/staff/conversations/:id/spectate",
    });
    expect(
      await screen.findByText(/无法旁观（需 senior\/engineer 权限）/),
    ).toBeInTheDocument();
  });

  it("点击「返回工作台」→ 跳列表", async () => {
    loginAsStaff("s_alice", "senior");
    renderWithRouter(<SpectateRoute />, {
      initialPath: "/staff/conversations/1/spectate",
      path: "/staff/conversations/:id/spectate",
      extraRoutes: [
        { path: "/staff/conversations", element: <div data-testid="list-stub">LIST</div> },
      ],
    });
    const back = await screen.findByRole("button", { name: /返回工作台/ });
    fireEvent.click(back);
    await waitFor(() => expect(screen.getByTestId("list-stub")).toBeInTheDocument());
  });
});
