// 403 跳转剧本：访问受保护页面但角色无权 → 路由级或后端返回 403 → UI 引导至 ForbiddenRoute。
// 由于本仓库没有统一的 403 拦截器（403 行为由各路由 alert/disable 决定），本剧本聚焦于：
//  - 路径 /403 渲染 ForbiddenRoute
//  - ForbiddenRoute「返回工作台」可跳列表
//  - 普通 agent 进入需要管理权限的页面（DashboardRoute）→ 看到「需要管理权限」alert，且不调接口

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App as AntdApp, ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { DashboardRoute } from "@/routes/admin/DashboardRoute";
import { ForbiddenRoute } from "@/routes/ForbiddenRoute";

import { installFetch, mockFetch, resetFetch } from "../helpers/fetchMock";
import { loginAsStaff, logoutStaff } from "../helpers/session";

function renderApp(initialPath = "/") {
  return render(
    <ConfigProvider locale={zhCN}>
      <AntdApp>
        <MemoryRouter initialEntries={[initialPath]}>
          <Routes>
            <Route path="/403" element={<ForbiddenRoute />} />
            <Route path="/admin/dashboard" element={<DashboardRoute />} />
            <Route
              path="/staff/conversations"
              element={<div data-testid="conv-list">CONV_LIST</div>}
            />
          </Routes>
        </MemoryRouter>
      </AntdApp>
    </ConfigProvider>,
  );
}

describe("integration: 403", () => {
  beforeEach(() => {
    installFetch();
  });
  afterEach(() => {
    resetFetch();
    logoutStaff();
    vi.restoreAllMocks();
  });

  it("/403 → 渲染 ForbiddenRoute；返回工作台跳列表", async () => {
    renderApp("/403");
    expect(screen.getByText(/403/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /返回工作台/ }));
    await waitFor(() => expect(screen.getByTestId("conv-list")).toBeInTheDocument());
  });

  it("agent 进入 /admin/dashboard → 看到「需要管理权限」，不调 overview 接口", async () => {
    loginAsStaff("s_alice", "agent");
    const calls: Request[] = [];
    mockFetch("GET", "/admin/api/v1/dashboard/overview", (req) => {
      calls.push(req);
      return new Response("", { status: 500 });
    });
    renderApp("/admin/dashboard");
    expect(await screen.findByText("需要管理权限")).toBeInTheDocument();
    // 不应触发任何对 overview 的请求
    await new Promise((r) => setTimeout(r, 20));
    expect(calls.length).toBe(0);
  });
});
