// ShiftsRoute：排班管理。
// 用例：
//  1) 非授权 → Alert
//  2) 授权加载：表格行
//  3) 空 → 「暂无排班」
//  4) 接口失败 → Alert
//  5) 「新建排班」抽屉打开

import { fireEvent, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ShiftsRoute } from "@/routes/admin/ShiftsRoute";

import {
  installFetch,
  jsonResponse,
  mockFetch,
  resetFetch,
} from "../../helpers/fetchMock";
import { renderWithRouter } from "../../helpers/render";
import { loginAsStaff, logoutStaff } from "../../helpers/session";

const shifts = [
  {
    id: 11,
    staff_id: "s_alice",
    start_at: "2026-01-01 09:00:00",
    end_at: "2026-01-01 18:00:00",
    created_at: "2025-12-31T00:00:00Z",
  },
];

describe("ShiftsRoute", () => {
  beforeEach(() => {
    installFetch();
  });
  afterEach(() => {
    resetFetch();
    logoutStaff();
    vi.restoreAllMocks();
  });

  it("非授权 → Alert", async () => {
    loginAsStaff("s_alice", "agent");
    renderWithRouter(<ShiftsRoute />, { path: "/admin/shifts" });
    expect(await screen.findByText("需要主管或管理员权限")).toBeInTheDocument();
  });

  it("授权加载渲染行", async () => {
    loginAsStaff("s_admin", "admin");
    mockFetch("GET", "/admin/api/v1/shifts", () => jsonResponse({ shifts }));
    renderWithRouter(<ShiftsRoute />, { path: "/admin/shifts" });
    expect(await screen.findByText("s_alice")).toBeInTheDocument();
  });

  it("空 → 暂无排班", async () => {
    loginAsStaff("s_admin", "admin");
    mockFetch("GET", "/admin/api/v1/shifts", () => jsonResponse({ shifts: [] }));
    renderWithRouter(<ShiftsRoute />, { path: "/admin/shifts" });
    expect(await screen.findByText("暂无排班")).toBeInTheDocument();
  });

  it("接口失败 → Alert", async () => {
    loginAsStaff("s_admin", "admin");
    mockFetch("GET", "/admin/api/v1/shifts", () => new Response("", { status: 500 }));
    renderWithRouter(<ShiftsRoute />, { path: "/admin/shifts" });
    expect(await screen.findByText(/list 500/)).toBeInTheDocument();
  });

  it("「新建排班」抽屉打开（含 staff_id 输入）", async () => {
    loginAsStaff("s_admin", "admin");
    mockFetch("GET", "/admin/api/v1/shifts", () => jsonResponse({ shifts: [] }));
    renderWithRouter(<ShiftsRoute />, { path: "/admin/shifts" });
    await screen.findByText("暂无排班");
    fireEvent.click(screen.getByRole("button", { name: /新建排班/ }));
    expect(await screen.findByPlaceholderText("staff_id")).toBeInTheDocument();
  });
});
