// TicketsRoute：工单列表（只读镜像）。
// 用例：
//  1) 未登录跳 /staff/login
//  2) 默认加载渲染表格
//  3) 加载错 → Alert
//  4) 空数据 → 「暂无工单」
//  5) 工单 ID 链接 href 正确
//  6) 状态切换 → 重新请求（status 参数，4 tab 各自精确传值）
//  7) 严重度筛选
//  8) 搜索过滤

import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TicketsRoute } from "@/routes/staff/TicketsRoute";

import {
  installFetch,
  jsonResponse,
  mockFetch,
  resetFetch,
} from "../../helpers/fetchMock";
import { renderWithRouter } from "../../helpers/render";
import { loginAsStaff, logoutStaff } from "../../helpers/session";

function ticket(extra: Partial<{ external_id: string; severity: string; status: string }> = {}) {
  return {
    external_id: extra.external_id ?? "TIK-001",
    category: "bug",
    severity: extra.severity ?? "p1",
    conversation_id: 50,
    created_at: "2026-01-01T00:00:00Z",
    status: extra.status ?? "pending",
    closed: false,
  };
}

describe("TicketsRoute", () => {
  beforeEach(() => {
    installFetch();
    loginAsStaff("s_alice", "agent");
  });
  afterEach(() => {
    resetFetch();
    logoutStaff();
    vi.restoreAllMocks();
  });

  it("未登录 → 跳 /staff/login", async () => {
    logoutStaff();
    renderWithRouter(<TicketsRoute />, {
      initialPath: "/staff/tickets",
      path: "/staff/tickets",
      extraRoutes: [{ path: "/staff/login", element: <div data-testid="login">LOGIN</div> }],
    });
    expect(await screen.findByTestId("login")).toBeInTheDocument();
  });

  it("默认加载：渲染表格行", async () => {
    mockFetch("GET", "/staff/api/v1/tickets", () =>
      jsonResponse({ tickets: [ticket(), ticket({ external_id: "TIK-002", severity: "p0" })] }),
    );
    renderWithRouter(<TicketsRoute />, { path: "/staff/tickets" });
    expect(await screen.findByText("TIK-001")).toBeInTheDocument();
    expect(screen.getByText("TIK-002")).toBeInTheDocument();
  });

  it("空数据：「暂无工单」", async () => {
    mockFetch("GET", "/staff/api/v1/tickets", () => jsonResponse({ tickets: [] }));
    renderWithRouter(<TicketsRoute />, { path: "/staff/tickets" });
    expect(await screen.findByText("暂无工单")).toBeInTheDocument();
  });

  it("接口 500 → Alert 加载失败", async () => {
    mockFetch("GET", "/staff/api/v1/tickets", () => new Response("", { status: 500 }));
    renderWithRouter(<TicketsRoute />, { path: "/staff/tickets" });
    expect(await screen.findByText("加载失败")).toBeInTheDocument();
  });

  it("工单链接 href 指向 /staff/tickets/{external_id}", async () => {
    mockFetch("GET", "/staff/api/v1/tickets", () => jsonResponse({ tickets: [ticket()] }));
    renderWithRouter(<TicketsRoute />, { path: "/staff/tickets" });
    const link = await screen.findByText("TIK-001");
    expect(link.closest("a")).toHaveAttribute("href", "/staff/tickets/TIK-001");
  });

  it.each([
    ["待处理", "pending"],
    ["进行中", "in_progress"],
    ["已解决", "resolved"],
    ["已关闭", "closed"],
  ])("点击 %s → 请求带 status=%s", async (label, status) => {
    const urls: string[] = [];
    mockFetch("GET", "/staff/api/v1/tickets", (req) => {
      urls.push(req.url);
      return jsonResponse({ tickets: [] });
    });
    renderWithRouter(<TicketsRoute />, { path: "/staff/tickets" });
    await screen.findByText("暂无工单");
    fireEvent.click(screen.getByText(label));
    await waitFor(() =>
      expect(urls.some((u) => u.includes(`status=${status}`))).toBe(true),
    );
  });

  it("默认（全部状态）→ 请求不带 status 参数", async () => {
    const urls: string[] = [];
    mockFetch("GET", "/staff/api/v1/tickets", (req) => {
      urls.push(req.url);
      return jsonResponse({ tickets: [] });
    });
    renderWithRouter(<TicketsRoute />, { path: "/staff/tickets" });
    await screen.findByText("暂无工单");
    expect(urls.every((u) => !u.includes("status="))).toBe(true);
  });

  it("严重度筛选 P0 → 请求带 severity=p0", async () => {
    const urls: string[] = [];
    mockFetch("GET", "/staff/api/v1/tickets", (req) => {
      urls.push(req.url);
      return jsonResponse({ tickets: [] });
    });
    renderWithRouter(<TicketsRoute />, { path: "/staff/tickets" });
    await screen.findByText("暂无工单");
    fireEvent.click(screen.getByText("P0"));
    await waitFor(() => expect(urls.some((u) => u.includes("severity=p0"))).toBe(true));
  });

  it("搜索：输入工单号过滤", async () => {
    mockFetch("GET", "/staff/api/v1/tickets", () =>
      jsonResponse({
        tickets: [
          ticket({ external_id: "TIK-001" }),
          ticket({ external_id: "BUG-099" }),
        ],
      }),
    );
    renderWithRouter(<TicketsRoute />, { path: "/staff/tickets" });
    await screen.findByText("TIK-001");
    fireEvent.change(screen.getByPlaceholderText(/搜索工单号/), {
      target: { value: "BUG" },
    });
    await waitFor(() => expect(screen.queryByText("TIK-001")).toBeNull());
    expect(screen.getByText("BUG-099")).toBeInTheDocument();
  });
});
