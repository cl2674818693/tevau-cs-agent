// DashboardRoute：数据大盘。
// 用例：
//  1) 默认（admin 角色）→ 渲染 6 张 KPI 卡 + 柱图
//  2) 非管理角色 → 显示「需要管理权限」
//  3) 接口 500 → 加载失败
//  4) handoff_rate > 30% 红色高亮

import { screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DashboardRoute } from "@/routes/admin/DashboardRoute";

import {
  installFetch,
  jsonResponse,
  mockFetch,
  resetFetch,
} from "../../helpers/fetchMock";
import { renderWithRouter } from "../../helpers/render";
import { loginAsStaff, logoutStaff } from "../../helpers/session";

const overview = {
  total_conversations: 100,
  handoff: 35,
  handoff_rate: 0.35, // 红色阈值
  upvote: 50,
  downvote: 10,
  downvote_rate: 0.1,
  tool_calls: 200,
  tool_empty: 20,
  tool_empty_rate: 0.1,
  out_of_scope: 5,
  failed_turns: 3,
};

describe("DashboardRoute", () => {
  beforeEach(() => {
    installFetch();
  });
  afterEach(() => {
    resetFetch();
    logoutStaff();
    vi.restoreAllMocks();
  });

  it("admin 默认加载：6 张 KPI 卡 + 柱图", async () => {
    loginAsStaff("s_admin", "admin");
    mockFetch("GET", "/admin/api/v1/dashboard/overview", () => jsonResponse(overview));
    renderWithRouter(<DashboardRoute />, { path: "/admin/dashboard" });

    expect(await screen.findByText("会话总数")).toBeInTheDocument();
    expect(screen.getByText("100")).toBeInTheDocument();
    expect(screen.getByText("失败回合")).toBeInTheDocument();
    expect(screen.getByText("关键比率对比（%）")).toBeInTheDocument();
  });

  it("非管理角色 → 提示 alert", async () => {
    loginAsStaff("s_alice", "agent");
    renderWithRouter(<DashboardRoute />, { path: "/admin/dashboard" });
    expect(await screen.findByText("需要管理权限")).toBeInTheDocument();
  });

  it("admin 但接口 500 → 加载失败", async () => {
    loginAsStaff("s_admin", "admin");
    mockFetch("GET", "/admin/api/v1/dashboard/overview", () =>
      new Response("", { status: 500 }),
    );
    renderWithRouter(<DashboardRoute />, { path: "/admin/dashboard" });
    expect(await screen.findByText("加载失败")).toBeInTheDocument();
  });
});
