import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getUsage, listPricing } from "../src/api/adminCost";
import { CostRoute } from "../src/routes/admin/CostRoute";

vi.mock("../src/api/adminCost");

function fakeJwt(role: string): string {
  return `h.${btoa(JSON.stringify({ role, sub: "AD1" }))}.s`;
}

const MOCK_ITEMS = [
  {
    model: "claude-sonnet-4-6",
    input_tokens: 10000,
    output_tokens: 5000,
    input_cost: 0.03,
    output_cost: 0.075,
    total_cost: 0.105,
    currency: "USD",
  },
  {
    model: "claude-haiku-3-5",
    input_tokens: 20000,
    output_tokens: 8000,
    input_cost: 0.005,
    output_cost: 0.004,
    total_cost: 0.009,
    currency: "USD",
  },
];

const MOCK_PRICING = [
  {
    model: "claude-sonnet-4-6",
    input_price_per_1k_x10000: 30000,
    output_price_per_1k_x10000: 150000,
    currency: "USD",
    updated_at: "2024-01-01T00:00:00Z",
  },
];

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

function renderRoute() {
  return render(
    <MemoryRouter initialEntries={["/admin/cost"]}>
      <Routes>
        <Route path="/admin/cost" element={<CostRoute />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("CostRoute", () => {
  it("blocks non-allowed roles", async () => {
    localStorage.setItem("staff_jwt", fakeJwt("agent"));
    renderRoute();
    await waitFor(() =>
      expect(screen.getByText("需要管理权限")).toBeInTheDocument(),
    );
    expect(getUsage).not.toHaveBeenCalled();
  });

  it("renders KPI cards for allowed role", async () => {
    localStorage.setItem("staff_jwt", fakeJwt("admin"));
    vi.mocked(getUsage).mockResolvedValue(MOCK_ITEMS);
    vi.mocked(listPricing).mockResolvedValue(MOCK_PRICING);

    renderRoute();

    await waitFor(() => expect(screen.getByText("总 Token 用量")).toBeInTheDocument());
    expect(screen.getAllByText(/API 费用/).length).toBeGreaterThan(0);
    expect(screen.getByText("平均单模型成本")).toBeInTheDocument();
    expect(screen.getByText("模型数")).toBeInTheDocument();
  });

  it("renders usage table with model rows", async () => {
    localStorage.setItem("staff_jwt", fakeJwt("engineer"));
    vi.mocked(getUsage).mockResolvedValue(MOCK_ITEMS);
    vi.mocked(listPricing).mockResolvedValue([]);

    renderRoute();

    await waitFor(() =>
      expect(screen.getByText("claude-sonnet-4-6")).toBeInTheDocument(),
    );
    expect(screen.getByText("claude-haiku-3-5")).toBeInTheDocument();
  });

  it("renders pricing table for engineer", async () => {
    localStorage.setItem("staff_jwt", fakeJwt("engineer"));
    vi.mocked(getUsage).mockResolvedValue([]);
    vi.mocked(listPricing).mockResolvedValue(MOCK_PRICING);

    renderRoute();

    await waitFor(() => expect(screen.getByText("单价配置")).toBeInTheDocument());
    expect(screen.getByText("30000")).toBeInTheDocument();
  });

  it("shows error alert on API failure", async () => {
    localStorage.setItem("staff_jwt", fakeJwt("admin"));
    vi.mocked(getUsage).mockRejectedValue(new Error("network"));
    vi.mocked(listPricing).mockRejectedValue(new Error("network"));

    renderRoute();

    await waitFor(() => expect(screen.getByText("加载失败")).toBeInTheDocument());
  });

  it("shows empty table message when no usage data", async () => {
    localStorage.setItem("staff_jwt", fakeJwt("admin"));
    vi.mocked(getUsage).mockResolvedValue([]);
    vi.mocked(listPricing).mockResolvedValue([]);

    renderRoute();

    await waitFor(() => expect(screen.getByText("暂无数据")).toBeInTheDocument());
  });

  it("total tokens aggregated correctly", async () => {
    localStorage.setItem("staff_jwt", fakeJwt("admin"));
    vi.mocked(getUsage).mockResolvedValue(MOCK_ITEMS);
    vi.mocked(listPricing).mockResolvedValue([]);

    renderRoute();

    // totalTokens = 10000+5000+20000+8000 = 43000
    await waitFor(() => expect(screen.getByText("43,000")).toBeInTheDocument());
  });

  it("manager role can view but not see pricing form", async () => {
    localStorage.setItem("staff_jwt", fakeJwt("manager"));
    vi.mocked(getUsage).mockResolvedValue(MOCK_ITEMS);
    vi.mocked(listPricing).mockResolvedValue(MOCK_PRICING);

    renderRoute();

    await waitFor(() => expect(screen.getByText("总 Token 用量")).toBeInTheDocument());
    // manager canEditPricing = false → no "保存单价" button
    expect(screen.queryByRole("button", { name: "保存单价" })).not.toBeInTheDocument();
  });
});
