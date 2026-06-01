import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getKpi } from "../src/api/staff";
import { KpiRoute } from "../src/routes/staff/KpiRoute";

vi.mock("../src/api/staff");

// JWT: { role: "agent", sub: "S001" }
function fakeJwt(sub = "S001"): string {
  return `h.${btoa(JSON.stringify({ role: "agent", sub }))}.s`;
}

const MOCK_KPI_RESULT = {
  from: null,
  to: null,
  staff: [
    {
      staff_id: "S001",
      takeovers: 42,
      releases: 5,
      resolved: 30,
      release_ratio: 0.12,
      resolved_ratio: 0.71,
      avg_handle_seconds: 185,
      transfers: 7,
      transfer_ratio: 0.17,
    },
    {
      staff_id: "S002",
      takeovers: 10,
      releases: 1,
      resolved: 8,
      release_ratio: 0.1,
      resolved_ratio: 0.8,
      avg_handle_seconds: 90,
    },
  ],
  ai_quality: {
    total_conversations: 100,
    handoff: 20,
    handoff_rate: 0.2,
    upvote: 30,
    downvote: 5,
    downvote_rate: 0.14,
    tool_calls: 50,
    tool_empty: 10,
    tool_empty_rate: 0.2,
    out_of_scope: 3,
    failed_turns: 2,
  },
};

beforeEach(() => {
  const store = new Map<string, string>();
  vi.stubGlobal("localStorage", {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
    removeItem: (k: string) => void store.delete(k),
    clear: () => store.clear(),
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

function renderRoute(sub = "S001") {
  localStorage.setItem("staff_jwt", fakeJwt(sub));
  return render(
    <MemoryRouter initialEntries={["/staff/kpi"]}>
      <Routes>
        <Route path="/staff/kpi" element={<KpiRoute />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("KpiRoute", () => {
  it("渲染页面标题", async () => {
    vi.mocked(getKpi).mockResolvedValue(MOCK_KPI_RESULT);
    renderRoute();
    expect(screen.getByText("我的 KPI")).toBeInTheDocument();
  });

  it("显示当前用户的 KPI 卡片", async () => {
    vi.mocked(getKpi).mockResolvedValue(MOCK_KPI_RESULT);
    renderRoute("S001");
    await waitFor(() => expect(screen.getByText("42")).toBeInTheDocument());
    expect(screen.getByText("接管数")).toBeInTheDocument();
    expect(screen.getByText("解决数")).toBeInTheDocument();
    expect(screen.getByText("转派数")).toBeInTheDocument();
    expect(screen.getByText("平均处理时长")).toBeInTheDocument();
    // 解决率
    expect(screen.getByText(/解决率 71%/)).toBeInTheDocument();
    // 平均时长
    expect(screen.getByText("3分5秒")).toBeInTheDocument();
  });

  it("无数据时显示空状态", async () => {
    vi.mocked(getKpi).mockResolvedValue({
      ...MOCK_KPI_RESULT,
      staff: [], // 当前用户不在列表中
    });
    renderRoute("S001");
    await waitFor(() => expect(screen.getByText(/暂无数据/)).toBeInTheDocument());
  });

  it("API 失败时显示错误提示", async () => {
    vi.mocked(getKpi).mockRejectedValue(new Error("network error"));
    renderRoute();
    await waitFor(() => expect(screen.getByText("加载失败")).toBeInTheDocument());
  });

  it("staffId 为 null 时也显示空状态（未登录）", async () => {
    vi.mocked(getKpi).mockResolvedValue(MOCK_KPI_RESULT);
    // 使用无效 JWT（无 sub）
    localStorage.setItem("staff_jwt", "invalid.token.here");
    render(
      <MemoryRouter initialEntries={["/staff/kpi"]}>
        <Routes>
          <Route path="/staff/kpi" element={<KpiRoute />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText(/暂无数据/)).toBeInTheDocument());
  });
});
