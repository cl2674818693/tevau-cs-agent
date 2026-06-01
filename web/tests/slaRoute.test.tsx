import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  listPolicies,
  listBreaches,
  createPolicy,
  deletePolicy,
  setPolicyActive,
} from "../src/api/adminSla";
import { SlaRoute } from "../src/routes/admin/SlaRoute";

vi.mock("../src/api/adminSla");

function fakeJwt(role: string): string {
  return `h.${btoa(JSON.stringify({ role, sub: "AD1" }))}.s`;
}

const MOCK_POLICIES = [
  {
    id: 1,
    metric: "take_time",
    threshold_seconds: 300,
    scope: "all",
    scope_value: null,
    active: 1,
    created_at: "2024-01-01T00:00:00Z",
  },
  {
    id: 2,
    metric: "resolve_time",
    threshold_seconds: 1800,
    scope: "all",
    scope_value: null,
    active: 0,
    created_at: "2024-01-02T00:00:00Z",
  },
];

const MOCK_BREACHES = [
  {
    conversation_id: 42,
    metric: "take_time",
    elapsed_seconds: 400,
    threshold_seconds: 300,
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
    <MemoryRouter initialEntries={["/admin/sla"]}>
      <Routes>
        <Route path="/admin/sla" element={<SlaRoute />} />
        <Route path="/staff/conversations/:id" element={<div>conv</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("SlaRoute", () => {
  it("blocks non-supervisor/non-admin roles", async () => {
    localStorage.setItem("staff_jwt", fakeJwt("agent"));
    renderRoute();
    await waitFor(() =>
      expect(screen.getByText("需要主管或管理员权限")).toBeInTheDocument(),
    );
    expect(listPolicies).not.toHaveBeenCalled();
  });

  it("renders KPI cards with data", async () => {
    localStorage.setItem("staff_jwt", fakeJwt("admin"));
    vi.mocked(listPolicies).mockResolvedValue(MOCK_POLICIES);
    vi.mocked(listBreaches).mockResolvedValue([]);

    renderRoute();

    await waitFor(() => expect(screen.getByText("达标率")).toBeInTheDocument());
    expect(screen.getByText("平均响应阈值")).toBeInTheDocument();
    expect(screen.getByText("未达标数")).toBeInTheDocument();
  });

  it("renders policy table columns", async () => {
    localStorage.setItem("staff_jwt", fakeJwt("admin"));
    vi.mocked(listPolicies).mockResolvedValue(MOCK_POLICIES);
    vi.mocked(listBreaches).mockResolvedValue([]);

    renderRoute();

    await waitFor(() => expect(screen.getByText("SLA 策略")).toBeInTheDocument());
    // "指标" appears in both policy and breach table headers
    expect(screen.getAllByText("指标").length).toBeGreaterThan(0);
    expect(screen.getAllByText("阈值（秒）").length).toBeGreaterThan(0);
    expect(screen.getAllByText("状态").length).toBeGreaterThan(0);
  });

  it("renders policy rows with correct metric labels", async () => {
    localStorage.setItem("staff_jwt", fakeJwt("admin"));
    vi.mocked(listPolicies).mockResolvedValue(MOCK_POLICIES);
    vi.mocked(listBreaches).mockResolvedValue([]);

    renderRoute();

    // getAllByText because "接管时长" appears in both select option and table cell
    await waitFor(() => expect(screen.getAllByText("接管时长").length).toBeGreaterThan(0));
    expect(screen.getAllByText("解决时长").length).toBeGreaterThan(0);
  });

  it("shows breach alert and breach table when breaches exist", async () => {
    localStorage.setItem("staff_jwt", fakeJwt("supervisor"));
    vi.mocked(listPolicies).mockResolvedValue(MOCK_POLICIES);
    vi.mocked(listBreaches).mockResolvedValue(MOCK_BREACHES);

    renderRoute();

    await waitFor(() =>
      expect(screen.getByText(/当前 1 个会话超时未处理/)).toBeInTheDocument(),
    );
    expect(screen.getByText("当前超时会话")).toBeInTheDocument();
    // overrun column: 400 - 300 = 100
    expect(screen.getByText("+100")).toBeInTheDocument();
  });

  it("shows empty breach table when no breaches", async () => {
    localStorage.setItem("staff_jwt", fakeJwt("admin"));
    vi.mocked(listPolicies).mockResolvedValue(MOCK_POLICIES);
    vi.mocked(listBreaches).mockResolvedValue([]);

    renderRoute();

    await waitFor(() => expect(screen.getByText("无超时会话")).toBeInTheDocument());
  });

  it("shows error alert on API failure", async () => {
    localStorage.setItem("staff_jwt", fakeJwt("admin"));
    vi.mocked(listPolicies).mockRejectedValue(new Error("network"));
    vi.mocked(listBreaches).mockRejectedValue(new Error("network"));

    renderRoute();

    await waitFor(() => expect(screen.getByText("加载失败")).toBeInTheDocument());
  });

  it("creates a policy and reloads", async () => {
    localStorage.setItem("staff_jwt", fakeJwt("admin"));
    vi.mocked(listPolicies).mockResolvedValue(MOCK_POLICIES);
    vi.mocked(listBreaches).mockResolvedValue([]);
    vi.mocked(createPolicy).mockResolvedValue(undefined);

    renderRoute();

    await waitFor(() => expect(screen.getByText("新增策略")).toBeInTheDocument());
    fireEvent.click(screen.getByText("新增策略"));

    await waitFor(() => expect(createPolicy).toHaveBeenCalledTimes(1));
    // reload triggers 2nd call
    await waitFor(() => expect(vi.mocked(listPolicies).mock.calls.length).toBeGreaterThan(1));
  });

  it("toggles policy active state", async () => {
    localStorage.setItem("staff_jwt", fakeJwt("admin"));
    vi.mocked(listPolicies).mockResolvedValue(MOCK_POLICIES);
    vi.mocked(listBreaches).mockResolvedValue([]);
    vi.mocked(setPolicyActive).mockResolvedValue(undefined);

    renderRoute();

    // Wait for table to load; "SLA 策略" section heading is unambiguous
    await waitFor(() => expect(screen.getByText("SLA 策略")).toBeInTheDocument());
    // First row is active=1, action button text is "停用" (as a button, not badge)
    const toggleBtns = screen.getAllByRole("button", { name: "停用" });
    fireEvent.click(toggleBtns[0]);

    await waitFor(() =>
      expect(setPolicyActive).toHaveBeenCalledWith(expect.any(String), 1, 0),
    );
  });

  it("deletes a policy", async () => {
    localStorage.setItem("staff_jwt", fakeJwt("admin"));
    vi.mocked(listPolicies).mockResolvedValue(MOCK_POLICIES);
    vi.mocked(listBreaches).mockResolvedValue([]);
    vi.mocked(deletePolicy).mockResolvedValue(undefined);

    renderRoute();

    await waitFor(() => expect(screen.getByText("SLA 策略")).toBeInTheDocument());
    const deleteBtns = screen.getAllByRole("button", { name: "删除" });
    fireEvent.click(deleteBtns[0]);

    await waitFor(() =>
      expect(deletePolicy).toHaveBeenCalledWith(expect.any(String), 1),
    );
  });

  it("compliance rate 100% when no breaches", async () => {
    localStorage.setItem("staff_jwt", fakeJwt("admin"));
    vi.mocked(listPolicies).mockResolvedValue(MOCK_POLICIES);
    vi.mocked(listBreaches).mockResolvedValue([]);

    renderRoute();

    // active policy = 1 (id=1, active=1), no breach → 100%
    await waitFor(() => expect(screen.getByText("100.0%")).toBeInTheDocument());
  });

  it("无 active 策略时达标率显示 — 而非 100%", async () => {
    localStorage.setItem("staff_jwt", fakeJwt("admin"));
    vi.mocked(listPolicies).mockResolvedValue([]);
    vi.mocked(listBreaches).mockResolvedValue([]);

    renderRoute();

    await waitFor(() => expect(screen.getByText("达标率")).toBeInTheDocument());
    // 0/0 不能展示为 100%；应展示 "—"
    expect(screen.queryByText("100.0%")).not.toBeInTheDocument();
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });
});
