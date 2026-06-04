// StaffAccountsRoute：客服账号管理。
// 用例：
//  1) 默认加载：表格行渲染
//  2) 接口 500 → Alert
//  3) 空 → 「暂无客服」
//  4) 点击「新建客服」→ 抽屉打开
//  5) 搜索过滤

import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { StaffAccountsRoute } from "@/routes/admin/StaffAccountsRoute";

import {
  installFetch,
  jsonResponse,
  mockFetch,
  resetFetch,
} from "../../helpers/fetchMock";
import { renderWithRouter } from "../../helpers/render";
import { loginAsStaff, logoutStaff } from "../../helpers/session";

const staffRows = [
  {
    id: 1,
    staff_id: "s_alice",
    display_name: "Alice",
    role: "agent",
    active: 1,
    created_at: "2026-01-01T00:00:00Z",
  },
];

describe("StaffAccountsRoute", () => {
  beforeEach(() => {
    installFetch();
    loginAsStaff("s_admin", "admin");
  });
  afterEach(() => {
    resetFetch();
    logoutStaff();
    vi.restoreAllMocks();
  });

  it("默认加载：表格行渲染", async () => {
    mockFetch("GET", "/admin/api/v1/staff", () => jsonResponse({ staff: staffRows }));

    renderWithRouter(<StaffAccountsRoute />, { path: "/admin/staff" });
    expect(await screen.findByText("s_alice")).toBeInTheDocument();
    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.getByText("客服")).toBeInTheDocument(); // role agent label
  });

  it("接口 500 → Alert 加载失败", async () => {
    mockFetch("GET", "/admin/api/v1/staff", () => new Response("", { status: 500 }));
    renderWithRouter(<StaffAccountsRoute />, { path: "/admin/staff" });
    expect(await screen.findByText(/list failed 500/)).toBeInTheDocument();
  });

  it("空 → 暂无客服", async () => {
    mockFetch("GET", "/admin/api/v1/staff", () => jsonResponse({ staff: [] }));
    renderWithRouter(<StaffAccountsRoute />, { path: "/admin/staff" });
    expect(await screen.findByText("暂无客服")).toBeInTheDocument();
  });

  it("点击「新建客服」→ 抽屉打开（含 staff_id 输入）", async () => {
    mockFetch("GET", "/admin/api/v1/staff", () => jsonResponse({ staff: [] }));
    renderWithRouter(<StaffAccountsRoute />, { path: "/admin/staff" });
    await screen.findByText("暂无客服");
    fireEvent.click(screen.getByRole("button", { name: /新建客服/ }));
    expect(await screen.findByPlaceholderText(/小写字母开头/)).toBeInTheDocument();
  });

  it("搜索 staff_id 过滤", async () => {
    mockFetch("GET", "/admin/api/v1/staff", () =>
      jsonResponse({
        staff: [
          ...staffRows,
          { ...staffRows[0], id: 2, staff_id: "s_bob", display_name: "Bob" },
        ],
      }),
    );
    renderWithRouter(<StaffAccountsRoute />, { path: "/admin/staff" });
    await screen.findByText("s_alice");
    fireEvent.change(screen.getByPlaceholderText(/搜索 staff_id/), {
      target: { value: "bob" },
    });
    await waitFor(() => expect(screen.queryByText("s_alice")).toBeNull());
    expect(screen.getByText("s_bob")).toBeInTheDocument();
  });
});
