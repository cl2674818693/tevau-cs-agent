// AppSidebar：RBAC 矩阵 + 静态 roles 决定哪些菜单可见。
import { App as AntApp } from "antd";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/staffFetch", () => ({ staffFetch: vi.fn() }));

import * as rbac from "@/api/adminRbac";
import { AppSidebar } from "@/components/app-shell/AppSidebar";
import { STAFF_TOKEN_KEY } from "@/hooks/useStaffSession";

import { clearLocalStorage } from "../../_helpers/storage";

function b64url(s: string): string {
  return btoa(s).replace(/=+$/, "").replace(/\+/g, "-").replace(/\//g, "_");
}
function makeJwt(payload: object): string {
  return `h.${b64url(JSON.stringify(payload))}.s`;
}

function wrap(ui: React.ReactNode) {
  return render(
    <MemoryRouter>
      <AntApp>{ui}</AntApp>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  clearLocalStorage();
  vi.restoreAllMocks();
});
afterEach(() => vi.restoreAllMocks());

describe("AppSidebar", () => {
  it("brand 标题渲染", () => {
    wrap(<AppSidebar />);
    expect(screen.getByText("Tevau 客服 AI 引擎")).toBeInTheDocument();
  });

  it("无 token / 无角色：仍展示 workbench（roles 未限定）", () => {
    wrap(<AppSidebar />);
    expect(screen.getByText("工作台")).toBeInTheDocument();
    expect(screen.getByText("会话")).toBeInTheDocument();
  });

  it("agent 角色：admin only 菜单不可见", async () => {
    localStorage.setItem(STAFF_TOKEN_KEY, makeJwt({ sub: "x", role: "agent" }));
    wrap(<AppSidebar />);
    expect(screen.getByText("工作台")).toBeInTheDocument();
    // admin 专属菜单不展示
    expect(screen.queryByText("客服账号")).toBeNull();
    expect(screen.queryByText("角色权限")).toBeNull();
  });

  it("admin 角色：拉 RBAC matrix 后按 matrix 决定 admin 菜单", async () => {
    localStorage.setItem(STAFF_TOKEN_KEY, makeJwt({ sub: "x", role: "admin" }));
    vi.spyOn(rbac, "getMatrix").mockResolvedValue({
      matrix: {
        admin: {
          "admin.dashboard": true,
          "admin.staff": false,
          "admin.rbac": true,
        },
      },
      roles: ["admin"],
      permission_keys: ["admin.dashboard", "admin.staff", "admin.rbac"],
    });
    wrap(<AppSidebar />);
    await waitFor(() => expect(rbac.getMatrix).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByText("数据大盘")).toBeInTheDocument());
    // matrix 中标记 false 的菜单隐藏
    expect(screen.queryByText("客服账号")).toBeNull();
    expect(screen.getByText("角色权限")).toBeInTheDocument();
  });

  it("点击菜单项：navigate + onNavigate 回调", async () => {
    const onNavigate = vi.fn();
    wrap(<AppSidebar onNavigate={onNavigate} />);
    fireEvent.click(screen.getByText("会话"));
    await waitFor(() => expect(onNavigate).toHaveBeenCalled());
  });
});
