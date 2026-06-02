// SlaRoute：SLA 策略 + 超时告警。
// 用例：
//  1) 非授权角色 → Alert
//  2) 授权 admin 默认加载：策略表格 + 超时表
//  3) 接口失败 → Alert 加载失败
//  4) 0 超时 → 「无超时会话」
//  5) 删除策略：点 Popconfirm 确定后 DELETE
//  6) 启用/停用 → PATCH

import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SlaRoute } from "@/routes/admin/SlaRoute";

import {
  installFetch,
  jsonResponse,
  mockFetch,
  resetFetch,
} from "../../helpers/fetchMock";
import { renderWithRouter } from "../../helpers/render";
import { loginAsStaff, logoutStaff } from "../../helpers/session";

const policies = [
  { id: 1, metric: "take_time", threshold_seconds: 300, scope: "all", scope_value: null, active: 1, created_at: "2026-01-01" },
];
const breaches = [
  { conversation_id: 7, metric: "take_time", elapsed_seconds: 400, threshold_seconds: 300 },
];

describe("SlaRoute", () => {
  beforeEach(() => {
    installFetch();
  });
  afterEach(() => {
    resetFetch();
    logoutStaff();
    vi.restoreAllMocks();
  });

  it("非授权 → Alert 需要主管或管理员权限", async () => {
    loginAsStaff("s_alice", "agent");
    renderWithRouter(<SlaRoute />, { path: "/admin/sla" });
    expect(await screen.findByText("需要主管或管理员权限")).toBeInTheDocument();
  });

  it("授权 supervisor 默认加载：策略与 breach 表格", async () => {
    loginAsStaff("s_sup", "supervisor");
    mockFetch("GET", "/admin/api/v1/sla/policies", () =>
      jsonResponse({ policies }),
    );
    mockFetch("GET", "/admin/api/v1/sla/breaches", () => jsonResponse({ breaches }));
    renderWithRouter(<SlaRoute />, { path: "/admin/sla" });
    expect(await screen.findByText(/SLA 策略/)).toBeInTheDocument();
    expect(screen.getAllByText("接管时长").length).toBeGreaterThan(0);
    expect(screen.getByText("当前超时会话")).toBeInTheDocument();
    // breach row
    expect(screen.getByText("#7")).toBeInTheDocument();
  });

  it("接口失败 → Alert 加载失败", async () => {
    loginAsStaff("s_admin", "admin");
    mockFetch("GET", "/admin/api/v1/sla/policies", () => new Response("", { status: 500 }));
    mockFetch("GET", "/admin/api/v1/sla/breaches", () => jsonResponse({ breaches: [] }));
    renderWithRouter(<SlaRoute />, { path: "/admin/sla" });
    expect(await screen.findByText("加载失败")).toBeInTheDocument();
  });

  it("无 breach → 「无超时会话」", async () => {
    loginAsStaff("s_admin", "admin");
    mockFetch("GET", "/admin/api/v1/sla/policies", () =>
      jsonResponse({ policies: [] }),
    );
    mockFetch("GET", "/admin/api/v1/sla/breaches", () => jsonResponse({ breaches: [] }));
    renderWithRouter(<SlaRoute />, { path: "/admin/sla" });
    expect(await screen.findByText("无超时会话")).toBeInTheDocument();
  });

  it("停用：点击「停用」→ PATCH active=0", async () => {
    loginAsStaff("s_admin", "admin");
    mockFetch("GET", "/admin/api/v1/sla/policies", () => jsonResponse({ policies }));
    mockFetch("GET", "/admin/api/v1/sla/breaches", () => jsonResponse({ breaches: [] }));
    const patchCalls: Request[] = [];
    mockFetch("PATCH", "/admin/api/v1/sla/policies/1", (req) => {
      patchCalls.push(req);
      return jsonResponse({ ok: true });
    });
    renderWithRouter(<SlaRoute />, { path: "/admin/sla" });
    fireEvent.click(await screen.findByRole("button", { name: /^停.?用$/ }));
    await waitFor(() => expect(patchCalls.length).toBe(1));
    const body = JSON.parse(await patchCalls[0].text());
    expect(body).toEqual({ active: 0 });
  });
});
