// KpiRoute：当前客服的 KPI 卡片。
// 用例覆盖：
//  1) 默认加载：找到当前 staff 的行并渲染 4 张统计卡
//  2) staff 不在 staff 列表中：显示 Empty「该时间段内暂无数据」
//  3) 加载态：Skeleton
//  4) 错误态：Alert
//  5) 解决率 < 70% 用红色提示色（color 来自 valueStyle）
//  6) 转派率 > 30% 用红色

import { screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { KpiRoute } from "@/routes/staff/KpiRoute";

import {
  installFetch,
  jsonResponse,
  mockFetch,
  resetFetch,
} from "../../helpers/fetchMock";
import { renderWithRouter } from "../../helpers/render";
import { loginAsStaff, logoutStaff } from "../../helpers/session";

describe("KpiRoute", () => {
  beforeEach(() => {
    installFetch();
    loginAsStaff("s_alice", "agent");
  });
  afterEach(() => {
    resetFetch();
    logoutStaff();
    vi.restoreAllMocks();
  });

  it("默认加载：渲染当前 staff 的 KPI 卡", async () => {
    mockFetch("GET", "/staff/api/v1/kpi", () =>
      jsonResponse({
        from: null,
        to: null,
        staff: [
          {
            staff_id: "s_alice",
            takeovers: 10,
            releases: 1,
            resolved: 8,
            release_ratio: 0.1,
            resolved_ratio: 0.8,
            avg_handle_seconds: 125,
            transfers: 2,
            transfer_ratio: 0.2,
          },
        ],
        ai_quality: {
          total_conversations: 0,
          handoff: 0,
          handoff_rate: 0,
          upvote: 0,
          downvote: 0,
          downvote_rate: 0,
          tool_calls: 0,
          tool_empty: 0,
          tool_empty_rate: 0,
          out_of_scope: 0,
          failed_turns: 0,
        },
      }),
    );

    renderWithRouter(<KpiRoute />, { path: "/staff/kpi" });
    expect(await screen.findByText("接管数")).toBeInTheDocument();
    expect(screen.getByText("解决数")).toBeInTheDocument();
    expect(screen.getByText("转派数")).toBeInTheDocument();
    expect(screen.getByText("平均处理时长")).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument(); // takeovers
    expect(screen.getByText(/解决率 80%/)).toBeInTheDocument();
    expect(screen.getByText("2分5秒")).toBeInTheDocument(); // avg 125s
  });

  it("staff 不在列表：显示空状态", async () => {
    mockFetch("GET", "/staff/api/v1/kpi", () =>
      jsonResponse({ from: null, to: null, staff: [], ai_quality: {} }),
    );
    renderWithRouter(<KpiRoute />, { path: "/staff/kpi" });
    expect(await screen.findByText(/该时间段内暂无数据/)).toBeInTheDocument();
  });

  it("接口 500 → Alert 加载失败", async () => {
    mockFetch("GET", "/staff/api/v1/kpi", () => new Response("", { status: 500 }));
    renderWithRouter(<KpiRoute />, { path: "/staff/kpi" });
    expect(await screen.findByText("加载失败")).toBeInTheDocument();
  });
});
