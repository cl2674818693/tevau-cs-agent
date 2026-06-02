// StaffLoginRoute：客服登录页。
// 用例覆盖：
//  1) 默认渲染：表单 + 标题
//  2) 提交合法表单 → 调 /staff/api/v1/auth/login，跳 /staff/conversations
//  3) 401 → message.error（不跳，因为登录页本身 401=账号错误）
//  4) 必填校验

import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { StaffLoginRoute } from "@/routes/staff/StaffLoginRoute";

import {
  installFetch,
  jsonResponse,
  mockFetch,
  resetFetch,
} from "../../helpers/fetchMock";
import { renderWithRouter } from "../../helpers/render";
import { buildStaffJwt, logoutStaff } from "../../helpers/session";

describe("StaffLoginRoute", () => {
  beforeEach(() => {
    installFetch();
    logoutStaff();
  });
  afterEach(() => {
    resetFetch();
    vi.restoreAllMocks();
  });

  it("默认渲染：表单 + 标题", () => {
    renderWithRouter(<StaffLoginRoute />, { path: "/staff/login" });
    expect(screen.getByText("Tevau 客服 AI 引擎")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("工号")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("密码")).toBeInTheDocument();
  });

  it("合法表单 → 调登录接口，token 写入并跳 /staff/conversations", async () => {
    const tok = buildStaffJwt("s_alice", "agent");
    const calls: Request[] = [];
    mockFetch("POST", "/staff/api/v1/auth/login", (req) => {
      calls.push(req);
      return jsonResponse({ token: tok, staff: { staff_id: "s_alice", display_name: "A", role: "agent" } });
    });

    renderWithRouter(<StaffLoginRoute />, {
      initialPath: "/staff/login",
      path: "/staff/login",
      extraRoutes: [{ path: "/staff/conversations", element: <div data-testid="list-stub">LIST</div> }],
    });

    fireEvent.change(screen.getByPlaceholderText("工号"), { target: { value: "s_alice" } });
    fireEvent.change(screen.getByPlaceholderText("密码"), { target: { value: "secret123" } });
    fireEvent.click(screen.getByRole("button", { name: /^登.?录$/ }));

    await waitFor(() => expect(calls.length).toBe(1));
    await waitFor(() => expect(screen.getByTestId("list-stub")).toBeInTheDocument());
    expect(localStorage.getItem("staff_jwt")).toBe(tok);
  });

  it("401 → 显示错误（不跳转）", async () => {
    mockFetch("POST", "/staff/api/v1/auth/login", () =>
      new Response("", { status: 401 }),
    );
    renderWithRouter(<StaffLoginRoute />, {
      initialPath: "/staff/login",
      path: "/staff/login",
      extraRoutes: [{ path: "/staff/conversations", element: <div data-testid="list-stub">LIST</div> }],
    });
    fireEvent.change(screen.getByPlaceholderText("工号"), { target: { value: "s_alice" } });
    fireEvent.change(screen.getByPlaceholderText("密码"), { target: { value: "wrong" } });
    fireEvent.click(screen.getByRole("button", { name: /^登.?录$/ }));

    expect(await screen.findByText(/工号或密码错误/)).toBeInTheDocument();
    expect(screen.queryByTestId("list-stub")).toBeNull();
  });

  it("校验：空表单不发请求", async () => {
    const calls: Request[] = [];
    mockFetch("POST", "/staff/api/v1/auth/login", (req) => {
      calls.push(req);
      return jsonResponse({});
    });
    renderWithRouter(<StaffLoginRoute />, { path: "/staff/login" });
    fireEvent.click(screen.getByRole("button", { name: /^登.?录$/ }));
    await new Promise((r) => setTimeout(r, 50));
    expect(calls.length).toBe(0);
  });
});
