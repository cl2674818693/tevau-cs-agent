// ConversationsListRoute：客服会话列表。
// 测试矩阵：
//  1) 默认加载：filter=human_pending → 表格渲染列与会话行
//  2) 加载态：API pending 时显示 Skeleton
//  3) 错误态：API 500 → Alert "加载失败"
//  4) 空数据：API [] → Table 空 placeholder
//  5) 401：staffFetch 触发 window.location 跳 /staff/login
//  6) 切到「全部」会重新请求（status 参数变化）
//  7) 「有风险信号」会带 risk_only=true 参数
//  8) 「我负责的」开关：仅显示 assigned_staff_id===staffId 行
//  9) 点击会话行链接跳详情（实际不挂详情路由，仅校验 href）

import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ConversationsListRoute } from "@/routes/staff/ConversationsListRoute";

import {
  installFetch,
  jsonResponse,
  mockFetch,
  pendingResponse,
  resetFetch,
} from "../../helpers/fetchMock";
import { renderWithRouter } from "../../helpers/render";
import { loginAsStaff, logoutStaff } from "../../helpers/session";

const sampleRows = [
  {
    id: 1001,
    user_type: "c",
    subject_id: "u_alpha",
    mode: "human_pending",
    assigned_staff_id: null,
    created_at: "2026-01-01 00:00:00",
    has_failed: 1,
    has_downvote: 0,
    has_out_of_scope: 0,
    has_empty_tool: 0,
    needs_review: 0,
  },
  {
    id: 1002,
    user_type: "b",
    subject_id: "1011010000068",
    mode: "human_takeover",
    assigned_staff_id: "s_alice",
    created_at: "2026-01-02 00:00:00",
    has_failed: 0,
    has_downvote: 1,
    has_out_of_scope: 0,
    has_empty_tool: 0,
    needs_review: 0,
  },
];

describe("ConversationsListRoute", () => {
  beforeEach(() => {
    installFetch();
    loginAsStaff("s_alice", "agent");
  });
  afterEach(() => {
    resetFetch();
    logoutStaff();
    vi.restoreAllMocks();
  });

  it("默认加载：渲染表格 + 列名 + 数据行", async () => {
    mockFetch("GET", "/staff/api/v1/conversations", () => jsonResponse(sampleRows));
    renderWithRouter(<ConversationsListRoute />, { path: "/staff/conversations" });

    expect(await screen.findByText("#1001")).toBeInTheDocument();
    expect(screen.getByText("#1002")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /会话 ID/ })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /负责人/ })).toBeInTheDocument();
    // 风险角标
    expect(screen.getByText("失败")).toBeInTheDocument();
    expect(screen.getByText("差评")).toBeInTheDocument();
  });

  it("加载态：API pending 时显示 Skeleton 卡片", () => {
    mockFetch("GET", "/staff/api/v1/conversations", () => pendingResponse());
    const { container } = renderWithRouter(<ConversationsListRoute />, {
      path: "/staff/conversations",
    });
    // antd Skeleton 渲染 .ant-skeleton 容器
    expect(container.querySelector(".ant-skeleton")).toBeTruthy();
  });

  it("错误态：API 500 → Alert 加载失败", async () => {
    mockFetch("GET", "/staff/api/v1/conversations", () => new Response("", { status: 500 }));
    renderWithRouter(<ConversationsListRoute />, { path: "/staff/conversations" });
    expect(await screen.findByText("加载失败")).toBeInTheDocument();
  });

  it("空数据：API [] → 空文案", async () => {
    mockFetch("GET", "/staff/api/v1/conversations", () => jsonResponse([]));
    renderWithRouter(<ConversationsListRoute />, { path: "/staff/conversations" });
    expect(await screen.findByText("暂无会话")).toBeInTheDocument();
  });

  it("401 → 触发 staffFetch 重定向到 /staff/login（清 token）", async () => {
    // hijack window.location.href setter（用 configurable: true 让 afterEach 可还原）
    const orig = window.location;
    const hrefSpy = vi.fn();
    Object.defineProperty(window, "location", {
      writable: true,
      configurable: true,
      value: {
        ...orig,
        pathname: "/staff/conversations",
        get href() {
          return orig.href;
        },
        set href(v: string) {
          hrefSpy(v);
        },
      },
    });

    try {
      mockFetch("GET", "/staff/api/v1/conversations", () => new Response("", { status: 401 }));
      renderWithRouter(<ConversationsListRoute />, { path: "/staff/conversations" });

      await waitFor(() => expect(hrefSpy).toHaveBeenCalledWith("/staff/login"));
      expect(localStorage.getItem("staff_jwt")).toBeNull();
    } finally {
      Object.defineProperty(window, "location", {
        writable: true,
        configurable: true,
        value: orig,
      });
    }
  });

  it("切换到「全部」筛选 → 重新发请求且参数 status=all", async () => {
    const urls: string[] = [];
    mockFetch("GET", "/staff/api/v1/conversations", (req) => {
      urls.push(new URL(req.url).search);
      return jsonResponse(sampleRows);
    });
    renderWithRouter(<ConversationsListRoute />, { path: "/staff/conversations" });
    await screen.findByText("#1001");

    fireEvent.click(screen.getByText("全部"));
    await waitFor(() => expect(urls.length).toBeGreaterThanOrEqual(2));
    expect(urls.some((u) => u.includes("status=all"))).toBe(true);
  });

  it("「有风险信号」筛选会带 risk_only=true 参数", async () => {
    const urls: string[] = [];
    mockFetch("GET", "/staff/api/v1/conversations", (req) => {
      urls.push(req.url);
      return jsonResponse(sampleRows);
    });
    renderWithRouter(<ConversationsListRoute />, { path: "/staff/conversations" });
    await screen.findByText("#1001");

    fireEvent.click(screen.getByText("有风险信号"));
    await waitFor(() => expect(urls.some((u) => u.includes("risk_only=true"))).toBe(true));
  });

  it("「我负责的」开关：只显示 assigned 给当前 staffId 的行", async () => {
    mockFetch("GET", "/staff/api/v1/conversations", () => jsonResponse(sampleRows));
    renderWithRouter(<ConversationsListRoute />, { path: "/staff/conversations" });
    await screen.findByText("#1001");

    fireEvent.click(screen.getByRole("switch"));
    // 1001 assigned=null，被过滤；1002 assigned=s_alice 仍在
    await waitFor(() => expect(screen.queryByText("#1001")).toBeNull());
    expect(screen.getByText("#1002")).toBeInTheDocument();
  });

  it("会话 ID 列是指向 /staff/conversations/{id} 的链接", async () => {
    mockFetch("GET", "/staff/api/v1/conversations", () => jsonResponse(sampleRows));
    renderWithRouter(<ConversationsListRoute />, { path: "/staff/conversations" });
    const link = await screen.findByText("#1001");
    const a = link.closest("a")!;
    expect(a).toHaveAttribute("href", "/staff/conversations/1001");
  });

  it("搜索 Subject ID：过滤匹配行", async () => {
    mockFetch("GET", "/staff/api/v1/conversations", () => jsonResponse(sampleRows));
    renderWithRouter(<ConversationsListRoute />, { path: "/staff/conversations" });
    await screen.findByText("#1001");

    const search = screen.getByPlaceholderText(/搜索 Subject ID/);
    fireEvent.change(search, { target: { value: "1011010" } });
    await waitFor(() => expect(screen.queryByText("#1001")).toBeNull());
    // 1002 的 subject_id 含 1011010 仍在
    const row1002 = screen.getByText("#1002");
    expect(within(row1002.closest("tr")!).getByText(/1011010000068/)).toBeInTheDocument();
  });
});
