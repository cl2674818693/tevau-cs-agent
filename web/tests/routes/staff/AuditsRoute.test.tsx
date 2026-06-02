// AuditsRoute：跨会话工具审计。
// 用例覆盖：
//  1) 默认加载：渲染表格
//  2) 空数据：locale.emptyText
//  3) 错误态：Alert
//  4) 工具下拉切换：触发新请求带 tool_name
//  5) 「只看被拒」点击：触发请求带 rejected=true
//  6) 「只看空结果」：empty_only=true
//  7) 输入会话号：conversation_id 参数
//  8) 行内会话链接 href 正确

import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuditsRoute } from "@/routes/staff/AuditsRoute";

import {
  installFetch,
  jsonResponse,
  mockFetch,
  resetFetch,
} from "../../helpers/fetchMock";
import { renderWithRouter } from "../../helpers/render";
import { loginAsStaff, logoutStaff } from "../../helpers/session";

function sample(extra: Partial<{ tool_name: string; rejected: number; is_empty: number }> = {}) {
  return {
    id: 1,
    conversation_id: 200,
    tool_name: extra.tool_name ?? "query_user",
    params_json: "{}",
    result_size: 100,
    duration_ms: 30,
    rejected: extra.rejected ?? 0,
    reject_reason: null,
    created_at: "2026-01-01 00:00:00",
    result_count: 1,
    is_empty: extra.is_empty ?? 0,
    subject_id: "u_alpha",
    user_type: "c",
  };
}

describe("AuditsRoute", () => {
  beforeEach(() => {
    installFetch();
    loginAsStaff("s_alice", "senior");
  });
  afterEach(() => {
    resetFetch();
    logoutStaff();
    vi.restoreAllMocks();
  });

  it("默认加载：渲染表格 + 工具名列", async () => {
    mockFetch("GET", "/staff/api/v1/audits/recent", () =>
      jsonResponse({ audits: [sample(), sample({ tool_name: "query_card" })], total: 2, page: 1, limit: 100 }),
    );
    renderWithRouter(<AuditsRoute />, { path: "/staff/audits" });

    expect(await screen.findByText("query_user")).toBeInTheDocument();
    expect(screen.getByText("query_card")).toBeInTheDocument();
  });

  it("空数据：显示「暂无记录」", async () => {
    mockFetch("GET", "/staff/api/v1/audits/recent", () =>
      jsonResponse({ audits: [], total: 0, page: 1, limit: 100 }),
    );
    renderWithRouter(<AuditsRoute />, { path: "/staff/audits" });
    expect(await screen.findByText("暂无记录")).toBeInTheDocument();
  });

  it("接口 500 → Alert 加载失败", async () => {
    mockFetch("GET", "/staff/api/v1/audits/recent", () =>
      new Response("", { status: 500 }),
    );
    renderWithRouter(<AuditsRoute />, { path: "/staff/audits" });
    expect(await screen.findByText("加载失败")).toBeInTheDocument();
  });

  it("点击「只看被拒」→ 请求带 rejected=true", async () => {
    const urls: string[] = [];
    mockFetch("GET", "/staff/api/v1/audits/recent", (req) => {
      urls.push(req.url);
      return jsonResponse({ audits: [], total: 0, page: 1, limit: 100 });
    });
    renderWithRouter(<AuditsRoute />, { path: "/staff/audits" });
    await screen.findByText("暂无记录");

    fireEvent.click(screen.getByRole("button", { name: /只看被拒/ }));
    await waitFor(() => expect(urls.some((u) => u.includes("rejected=true"))).toBe(true));
  });

  it("点击「只看空结果」→ 请求带 empty_only=true", async () => {
    const urls: string[] = [];
    mockFetch("GET", "/staff/api/v1/audits/recent", (req) => {
      urls.push(req.url);
      return jsonResponse({ audits: [], total: 0, page: 1, limit: 100 });
    });
    renderWithRouter(<AuditsRoute />, { path: "/staff/audits" });
    await screen.findByText("暂无记录");
    fireEvent.click(screen.getByRole("button", { name: /只看空结果/ }));
    await waitFor(() => expect(urls.some((u) => u.includes("empty_only=true"))).toBe(true));
  });

  it("输入会话号 → 请求带 conversation_id 参数", async () => {
    const urls: string[] = [];
    mockFetch("GET", "/staff/api/v1/audits/recent", (req) => {
      urls.push(req.url);
      return jsonResponse({ audits: [], total: 0, page: 1, limit: 100 });
    });
    renderWithRouter(<AuditsRoute />, { path: "/staff/audits" });
    await screen.findByText("暂无记录");

    fireEvent.change(screen.getByPlaceholderText("会话号"), { target: { value: "789" } });
    await waitFor(() => expect(urls.some((u) => u.includes("conversation_id=789"))).toBe(true));
  });

  it("会话列 → 渲染指向 /staff/conversations/{id}/logs 的链接", async () => {
    mockFetch("GET", "/staff/api/v1/audits/recent", () =>
      jsonResponse({ audits: [sample()], total: 1, page: 1, limit: 100 }),
    );
    renderWithRouter(<AuditsRoute />, { path: "/staff/audits" });
    const link = await screen.findByText("#200");
    expect(link.closest("a")).toHaveAttribute("href", "/staff/conversations/200/logs");
  });
});
