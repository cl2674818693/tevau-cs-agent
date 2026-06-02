// StaffGroupsRoute：客服分组管理。
// 用例：
//  1) 默认加载渲染行
//  2) 空 → 「暂无分组」
//  3) 接口失败 → Alert
//  4) 点击「新建分组」打开抽屉
//  5) 搜索过滤

import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { StaffGroupsRoute } from "@/routes/admin/StaffGroupsRoute";

import {
  installFetch,
  jsonResponse,
  mockFetch,
  resetFetch,
} from "../../helpers/fetchMock";
import { renderWithRouter } from "../../helpers/render";
import { loginAsStaff, logoutStaff } from "../../helpers/session";

const groups = [
  { id: 1, name: "技术组", description: "工程师团队", active: 1, created_at: "2026-01-01T00:00:00Z" },
];

describe("StaffGroupsRoute", () => {
  beforeEach(() => {
    installFetch();
    loginAsStaff("s_admin", "admin");
  });
  afterEach(() => {
    resetFetch();
    logoutStaff();
    vi.restoreAllMocks();
  });

  it("默认加载：渲染行", async () => {
    mockFetch("GET", "/admin/api/v1/staff-groups", () => jsonResponse({ groups }));
    renderWithRouter(<StaffGroupsRoute />, { path: "/admin/staff-groups" });
    expect(await screen.findByText("技术组")).toBeInTheDocument();
    expect(screen.getByText("工程师团队")).toBeInTheDocument();
  });

  it("空 → 「暂无分组」", async () => {
    mockFetch("GET", "/admin/api/v1/staff-groups", () => jsonResponse({ groups: [] }));
    renderWithRouter(<StaffGroupsRoute />, { path: "/admin/staff-groups" });
    expect(await screen.findByText("暂无分组")).toBeInTheDocument();
  });

  it("接口失败 → Alert", async () => {
    mockFetch("GET", "/admin/api/v1/staff-groups", () => new Response("", { status: 500 }));
    renderWithRouter(<StaffGroupsRoute />, { path: "/admin/staff-groups" });
    expect(await screen.findByText(/list 500/)).toBeInTheDocument();
  });

  it("「新建分组」打开抽屉", async () => {
    mockFetch("GET", "/admin/api/v1/staff-groups", () => jsonResponse({ groups: [] }));
    renderWithRouter(<StaffGroupsRoute />, { path: "/admin/staff-groups" });
    await screen.findByText("暂无分组");
    fireEvent.click(screen.getByRole("button", { name: /新建分组/ }));
    expect(await screen.findByPlaceholderText("分组名称")).toBeInTheDocument();
  });

  it("搜索过滤名称", async () => {
    mockFetch("GET", "/admin/api/v1/staff-groups", () =>
      jsonResponse({
        groups: [
          ...groups,
          { ...groups[0], id: 2, name: "运营组", description: "ops" },
        ],
      }),
    );
    renderWithRouter(<StaffGroupsRoute />, { path: "/admin/staff-groups" });
    await screen.findByText("技术组");
    fireEvent.change(screen.getByPlaceholderText(/搜索分组名/), {
      target: { value: "运营" },
    });
    await waitFor(() => expect(screen.queryByText("技术组")).toBeNull());
    expect(screen.getByText("运营组")).toBeInTheDocument();
  });
});
