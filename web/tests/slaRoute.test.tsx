import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { App as AntdApp, ConfigProvider } from "antd";
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
  // antd v6: App.useApp() 需要 <AntdApp> 包裹才能拿到 message/notification context，
  // 否则 form 提交流里的 message.success() 会跳过 onCreated()。
  return render(
    <ConfigProvider>
      <AntdApp>
        <MemoryRouter initialEntries={["/admin/sla"]}>
          <Routes>
            <Route path="/admin/sla" element={<SlaRoute />} />
            <Route path="/staff/conversations/:id" element={<div>conv</div>} />
          </Routes>
        </MemoryRouter>
      </AntdApp>
    </ConfigProvider>,
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

    // antd Form 的提交按钮 — 用 role 取，避免点到 "新增策略" 标题文字
    const submitBtn = await screen.findByRole("button", { name: "新增策略" });
    fireEvent.click(submitBtn);

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
    // 表格里的"删除"按钮 → 触发 antd Popconfirm 弹出
    const rowDeleteBtn = screen.getAllByRole("button", { name: "删除" })[0];
    fireEvent.click(rowDeleteBtn);

    // Popconfirm 弹层里的确认按钮（与触发器异名，定位明确）
    const confirmBtn = await screen.findByRole("button", { name: "确定删除" });
    fireEvent.click(confirmBtn);

    await waitFor(() =>
      expect(deletePolicy).toHaveBeenCalledWith(expect.any(String), 1),
    );
  });

  it("compliance rate 100% when no breaches", async () => {
    localStorage.setItem("staff_jwt", fakeJwt("admin"));
    vi.mocked(listPolicies).mockResolvedValue(MOCK_POLICIES);
    vi.mocked(listBreaches).mockResolvedValue([]);

    const { container } = renderRoute();

    // active policy = 1 (id=1, active=1), no breach → 100%
    // antd Statistic 把数字/小数/后缀拆成 3 个 span，整 div 的 textContent = "100.0%"
    await waitFor(() => {
      const valueEl = container.querySelector(".ant-statistic-content");
      expect(valueEl?.textContent?.replace(/\s/g, "")).toContain("100.0%");
    });
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
