// PresenceRoute：在线状态（supervisor/admin）。
// 用例：
//  1) 默认（supervisor）→ 渲染列表 + 列名
//  2) 非授权角色 → Alert「需要主管或管理员权限」
//  3) 接口 500 → Alert 错误消息
//  4) 搜索按 staff_id 过滤
//  5) 状态过滤：仅在线
//  6) 点击刷新 → 重新请求

import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PresenceRoute } from "@/routes/admin/PresenceRoute";

import {
  installFetch,
  jsonResponse,
  mockFetch,
  resetFetch,
} from "../../helpers/fetchMock";
import { renderWithRouter } from "../../helpers/render";
import { loginAsStaff, logoutStaff } from "../../helpers/session";

const rows = [
  { staff_id: "s_alice", status: "online", last_seen_at: "2026-01-01T00:00:00Z" },
  { staff_id: "s_bob", status: "away", last_seen_at: "2026-01-01T00:01:00Z" },
];

describe("PresenceRoute", () => {
  beforeEach(() => {
    installFetch();
  });
  afterEach(() => {
    resetFetch();
    logoutStaff();
    vi.restoreAllMocks();
  });

  it("supervisor 默认加载", async () => {
    loginAsStaff("s_sup", "supervisor");
    mockFetch("GET", "/admin/api/v1/presence", () => jsonResponse({ all: rows, active: rows.slice(0, 1) }));
    renderWithRouter(<PresenceRoute />, { path: "/admin/presence" });
    expect(await screen.findByText("s_alice")).toBeInTheDocument();
    expect(screen.getByText("s_bob")).toBeInTheDocument();
    expect(screen.getByText("在线")).toBeInTheDocument();
    expect(screen.getByText("离开")).toBeInTheDocument();
  });

  it("普通角色 → 显示「需要主管或管理员权限」", async () => {
    loginAsStaff("s_alice", "agent");
    renderWithRouter(<PresenceRoute />, { path: "/admin/presence" });
    expect(
      await screen.findByText("需要主管或管理员权限"),
    ).toBeInTheDocument();
  });

  it("接口失败 → Alert", async () => {
    loginAsStaff("s_admin", "admin");
    mockFetch("GET", "/admin/api/v1/presence", () => new Response("", { status: 500 }));
    renderWithRouter(<PresenceRoute />, { path: "/admin/presence" });
    expect(await screen.findByText(/presence 500/)).toBeInTheDocument();
  });

  it("按 staff_id 搜索过滤", async () => {
    loginAsStaff("s_admin", "admin");
    mockFetch("GET", "/admin/api/v1/presence", () =>
      jsonResponse({ all: rows, active: rows.slice(0, 1) }),
    );
    renderWithRouter(<PresenceRoute />, { path: "/admin/presence" });
    await screen.findByText("s_alice");
    fireEvent.change(screen.getByPlaceholderText(/按 staff_id 搜索/), {
      target: { value: "alice" },
    });
    await waitFor(() => expect(screen.queryByText("s_bob")).toBeNull());
    expect(screen.getByText("s_alice")).toBeInTheDocument();
  });

  it("点击刷新 → 重新请求", async () => {
    loginAsStaff("s_admin", "admin");
    let n = 0;
    mockFetch("GET", "/admin/api/v1/presence", () => {
      n += 1;
      return jsonResponse({ all: rows, active: [] });
    });
    renderWithRouter(<PresenceRoute />, { path: "/admin/presence" });
    await screen.findByText("s_alice");
    const before = n;
    fireEvent.click(screen.getByRole("button", { name: /刷新/ }));
    await waitFor(() => expect(n).toBe(before + 1));
  });
});
