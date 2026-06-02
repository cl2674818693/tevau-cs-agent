// BuLoginRoute：B 端主账户登录页。
// 用例覆盖：
//  1) 默认渲染（标题 / 副标题 / 必填校验）
//  2) 输入合法 ID 提交 → 调 /api/v1/auth/bu/login 并跳 /
//  3) 后端返回 4xx → 显示错误文案
//  4) 必填校验：不输入 ID 点提交不发请求
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { BuLoginRoute } from "@/routes/BuLoginRoute";

import { installFetch, jsonResponse, mockFetch, resetFetch } from "../../helpers/fetchMock";
import { renderWithRouter } from "../../helpers/render";

describe("BuLoginRoute", () => {
  beforeEach(() => {
    installFetch();
  });
  afterEach(() => {
    resetFetch();
    vi.restoreAllMocks();
  });

  it("默认渲染：标题、副标题、表单可见", () => {
    renderWithRouter(<BuLoginRoute />, { path: "/bu/login" });
    expect(screen.getByText("Tevau AI 客服")).toBeInTheDocument();
    expect(screen.getByText("合作伙伴技术支持")).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(/主账户 ID/),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /进入对话/ })).toBeInTheDocument();
  });

  it("happy path：提交合法 bu_id → 调登录接口并导航到 /", async () => {
    const calls: Request[] = [];
    mockFetch("POST", "/api/v1/auth/bu/login", async (req) => {
      calls.push(req);
      return jsonResponse({ ok: true });
    });

    renderWithRouter(<BuLoginRoute />, {
      initialPath: "/bu/login",
      path: "/bu/login",
      extraRoutes: [{ path: "/", element: <div data-testid="home">HOME</div> }],
    });

    fireEvent.change(screen.getByPlaceholderText(/主账户 ID/), {
      target: { value: " 1011010000068 " },
    });
    fireEvent.click(screen.getByRole("button", { name: /进入对话/ }));

    await waitFor(() => expect(calls.length).toBe(1));
    const body = JSON.parse((await calls[0].text()) || "{}");
    expect(body).toEqual({ bu_id: "1011010000068" }); // trim 生效
    await waitFor(() => expect(screen.getByTestId("home")).toBeInTheDocument());
  });

  it("后端 400 → 显示错误文案，不跳转", async () => {
    mockFetch("POST", "/api/v1/auth/bu/login", () =>
      new Response("账号不存在", { status: 400 }),
    );

    renderWithRouter(<BuLoginRoute />, {
      initialPath: "/bu/login",
      path: "/bu/login",
      extraRoutes: [{ path: "/", element: <div data-testid="home">HOME</div> }],
    });

    fireEvent.change(screen.getByPlaceholderText(/主账户 ID/), {
      target: { value: "bad_id" },
    });
    fireEvent.click(screen.getByRole("button", { name: /进入对话/ }));

    await waitFor(() =>
      expect(screen.getByText("账号不存在")).toBeInTheDocument(),
    );
    expect(screen.queryByTestId("home")).toBeNull();
  });

  it("校验：空表单不发请求", async () => {
    const calls: Request[] = [];
    mockFetch("POST", "/api/v1/auth/bu/login", async (req) => {
      calls.push(req);
      return jsonResponse({ ok: true });
    });
    renderWithRouter(<BuLoginRoute />, { path: "/bu/login" });

    fireEvent.click(screen.getByRole("button", { name: /进入对话/ }));
    // 等一帧给 antd Form 校验运行；不应触发请求
    await new Promise((r) => setTimeout(r, 50));
    expect(calls.length).toBe(0);
    expect(await screen.findByText("请输入主账户 ID")).toBeInTheDocument();
  });
});
