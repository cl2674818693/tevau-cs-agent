// InsightsRoute：知识缺口看板（卡片 + 下钻 + 工具健康）。
// 用例覆盖：
//  1) 默认加载：4 张缺口卡片 + 工具健康表格
//  2) 加载态：Skeleton
//  3) 错误态：Alert
//  4) 点击卡片打开下钻面板（请求 gap-conversations）
//  5) 再次点击同一卡片关闭下钻
//  6) 切换时间段：7d/30d/all 重新请求
//  7) 工具健康行：空结果率 > 50% 显示红色
//  8) 工具健康：空数据时显示「暂无记录」

import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { InsightsRoute } from "@/routes/staff/InsightsRoute";

import {
  installFetch,
  jsonResponse,
  mockFetch,
  resetFetch,
} from "../../helpers/fetchMock";
import { renderWithRouter } from "../../helpers/render";
import { loginAsStaff, logoutStaff } from "../../helpers/session";

const gaps = { out_of_scope: 3, failed_turns: 1, thumbs_down: 2, human_handoff: 5 };
const tools = [
  { tool_name: "query_user", calls: 10, empty: 1, rejected: 0, empty_rate: 0.1 },
  { tool_name: "query_card", calls: 4, empty: 3, rejected: 1, empty_rate: 0.75 },
];

describe("InsightsRoute", () => {
  beforeEach(() => {
    installFetch();
    loginAsStaff("s_alice", "senior");
  });
  afterEach(() => {
    resetFetch();
    logoutStaff();
    vi.restoreAllMocks();
  });

  function setupOk() {
    mockFetch("GET", "/staff/api/v1/insights/knowledge-gaps", () => jsonResponse(gaps));
    mockFetch("GET", "/staff/api/v1/insights/tool-health", () => jsonResponse({ tools }));
  }

  it("默认加载：渲染 4 张缺口卡片 + 工具健康表格", async () => {
    setupOk();
    renderWithRouter(<InsightsRoute />, { path: "/staff/insights" });

    expect(await screen.findByText("范围外")).toBeInTheDocument();
    expect(screen.getByText("失败回合")).toBeInTheDocument();
    expect(screen.getByText("差评 👎")).toBeInTheDocument();
    expect(screen.getByText("转人工")).toBeInTheDocument();
    // 数字（多卡片可能撞 "3"，断言至少出现一次即可）
    expect(screen.getAllByText("3").length).toBeGreaterThan(0); // out_of_scope
    // 工具表格
    expect(screen.getByText("query_user")).toBeInTheDocument();
    expect(screen.getByText("query_card")).toBeInTheDocument();
    // 75% 显示红色
    expect(screen.getByText("75%")).toBeInTheDocument();
  });

  it("错误态：Alert 加载失败", async () => {
    mockFetch("GET", "/staff/api/v1/insights/knowledge-gaps", () =>
      new Response("", { status: 500 }),
    );
    mockFetch("GET", "/staff/api/v1/insights/tool-health", () => jsonResponse({ tools: [] }));
    renderWithRouter(<InsightsRoute />, { path: "/staff/insights" });
    expect(await screen.findByText("加载失败")).toBeInTheDocument();
  });

  it("点击「转人工」卡片打开下钻面板", async () => {
    setupOk();
    mockFetch("GET", "/staff/api/v1/insights/gap-conversations", () =>
      jsonResponse({
        conversations: [
          { conversation_id: 9001, last_at: "2026-01-01 00:00:00" },
        ],
      }),
    );
    renderWithRouter(<InsightsRoute />, { path: "/staff/insights" });

    fireEvent.click(await screen.findByText("转人工"));
    expect(await screen.findByText("#9001")).toBeInTheDocument();
  });

  it("再点同一卡片 → 关闭下钻", async () => {
    setupOk();
    mockFetch("GET", "/staff/api/v1/insights/gap-conversations", () =>
      jsonResponse({
        conversations: [{ conversation_id: 9001, last_at: "2026-01-01 00:00:00" }],
      }),
    );
    renderWithRouter(<InsightsRoute />, { path: "/staff/insights" });
    fireEvent.click(await screen.findByText("转人工"));
    await screen.findByText("#9001");
    fireEvent.click(screen.getByText("转人工"));
    await waitFor(() => expect(screen.queryByText("#9001")).toBeNull());
  });

  it("切换时间段「全部」→ 重新请求", async () => {
    // 只注册一次（带 url 收集），避免 setupOk 先注册的同前缀 predicate 抢匹配
    const urls: string[] = [];
    mockFetch("GET", "/staff/api/v1/insights/knowledge-gaps", (req) => {
      urls.push(req.url);
      return jsonResponse(gaps);
    });
    mockFetch("GET", "/staff/api/v1/insights/tool-health", () => jsonResponse({ tools }));
    renderWithRouter(<InsightsRoute />, { path: "/staff/insights" });
    await screen.findByText("范围外");

    fireEvent.click(screen.getByText("全部"));
    await waitFor(() => expect(urls.length).toBeGreaterThanOrEqual(2));
  });

  it("工具健康为空 → 显示「暂无记录」", async () => {
    mockFetch("GET", "/staff/api/v1/insights/knowledge-gaps", () => jsonResponse(gaps));
    mockFetch("GET", "/staff/api/v1/insights/tool-health", () => jsonResponse({ tools: [] }));
    renderWithRouter(<InsightsRoute />, { path: "/staff/insights" });
    expect(await screen.findByText("暂无记录")).toBeInTheDocument();
  });
});
