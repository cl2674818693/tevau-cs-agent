// RbacRoute：角色权限矩阵（仅 admin）。
// 用例：
//  1) 非 admin → 显示「需要管理员权限」
//  2) admin 默认加载 → 渲染矩阵 + 复选框
//  3) 勾选/取消 → 本地 state 变更
//  4) 点击「重置」→ 矩阵回到服务端值
//  5) 点击「保存」→ 调 PUT

import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { RbacRoute } from "@/routes/admin/RbacRoute";

import {
  installFetch,
  jsonResponse,
  mockFetch,
  resetFetch,
} from "../../helpers/fetchMock";
import { renderWithRouter } from "../../helpers/render";
import { loginAsStaff, logoutStaff } from "../../helpers/session";

const matrix = {
  matrix: {
    agent: { "admin.dashboard": false, "admin.staff": false },
    admin: { "admin.dashboard": true, "admin.staff": true },
  },
  roles: ["agent", "admin"],
  permission_keys: ["admin.dashboard", "admin.staff"],
};

describe("RbacRoute", () => {
  beforeEach(() => {
    installFetch();
  });
  afterEach(() => {
    resetFetch();
    logoutStaff();
    vi.restoreAllMocks();
  });

  it("非 admin → 显示「需要管理员权限」", async () => {
    loginAsStaff("s_alice", "agent");
    renderWithRouter(<RbacRoute />, { path: "/admin/rbac" });
    expect(await screen.findByText(/需要管理员权限/)).toBeInTheDocument();
  });

  it("admin 默认加载：渲染矩阵 + 复选框", async () => {
    loginAsStaff("s_admin", "admin");
    mockFetch("GET", "/admin/api/v1/rbac/matrix", () => jsonResponse(matrix));
    renderWithRouter(<RbacRoute />, { path: "/admin/rbac" });
    expect(await screen.findAllByText("数据大盘")).not.toHaveLength(0);
    expect(screen.getAllByText("客服账号").length).toBeGreaterThan(0);
    // 4 个交叉格子（2 模块 × 2 角色）
    expect(screen.getAllByRole("checkbox").length).toBe(4);
  });

  it("勾选 → 状态变更（本地）", async () => {
    loginAsStaff("s_admin", "admin");
    mockFetch("GET", "/admin/api/v1/rbac/matrix", () => jsonResponse(matrix));
    renderWithRouter(<RbacRoute />, { path: "/admin/rbac" });

    const aria = await screen.findByLabelText("数据大盘/客服");
    expect(aria).not.toBeChecked();
    fireEvent.click(aria);
    expect(aria).toBeChecked();
  });

  it("点击「保存」→ PUT 调用", async () => {
    loginAsStaff("s_admin", "admin");
    mockFetch("GET", "/admin/api/v1/rbac/matrix", () => jsonResponse(matrix));
    const putCalls: Request[] = [];
    mockFetch("PUT", "/admin/api/v1/rbac/matrix", (req) => {
      putCalls.push(req);
      return jsonResponse({ ok: true });
    });
    renderWithRouter(<RbacRoute />, { path: "/admin/rbac" });
    await screen.findAllByText("数据大盘");

    fireEvent.click(screen.getByRole("button", { name: /^保.?存$/ }));
    await waitFor(() => expect(putCalls.length).toBe(1));
  });
});
