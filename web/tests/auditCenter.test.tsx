import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { listAudit } from "../src/api/adminAudit";
import { AuditCenterRoute } from "../src/routes/admin/AuditCenterRoute";

vi.mock("../src/api/adminAudit");

function fakeJwt(role: string): string {
  return `h.${btoa(JSON.stringify({ role, sub: "AD1" }))}.s`;
}

const MOCK_ENTRIES = [
  {
    id: 1,
    actor: "alice",
    action: "staff.create",
    target_type: "staff",
    target_id: "bob",
    detail_json: '{"note":"initial"}',
    created_at: "2024-03-15T10:00:00Z",
  },
  {
    id: 2,
    actor: "charlie",
    action: "ticket.close",
    target_type: "ticket",
    target_id: "T001",
    detail_json: null,
    created_at: "2024-03-16T12:30:00Z",
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
    <MemoryRouter initialEntries={["/admin/audit"]}>
      <Routes>
        <Route path="/admin/audit" element={<AuditCenterRoute />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("AuditCenterRoute", () => {
  it("blocks non-engineer/non-admin roles", async () => {
    localStorage.setItem("staff_jwt", fakeJwt("agent"));
    renderRoute();
    await waitFor(() =>
      expect(screen.getByText("需要工程或管理员权限")).toBeInTheDocument(),
    );
    expect(listAudit).not.toHaveBeenCalled();
  });

  it("renders table with data for engineer role", async () => {
    localStorage.setItem("staff_jwt", fakeJwt("engineer"));
    vi.mocked(listAudit).mockResolvedValue(MOCK_ENTRIES);

    renderRoute();

    await waitFor(() => expect(screen.getByText("alice")).toBeInTheDocument());
    expect(screen.getByText("staff.create")).toBeInTheDocument();
    expect(screen.getByText("charlie")).toBeInTheDocument();
    expect(screen.getByText("ticket.close")).toBeInTheDocument();
  });

  it("renders table for admin role", async () => {
    localStorage.setItem("staff_jwt", fakeJwt("admin"));
    vi.mocked(listAudit).mockResolvedValue(MOCK_ENTRIES);

    renderRoute();

    await waitFor(() => expect(screen.getByText("alice")).toBeInTheDocument());
  });

  it("shows target as type:id", async () => {
    localStorage.setItem("staff_jwt", fakeJwt("engineer"));
    vi.mocked(listAudit).mockResolvedValue(MOCK_ENTRIES);

    renderRoute();

    await waitFor(() => expect(screen.getByText("staff:bob")).toBeInTheDocument());
    expect(screen.getByText("ticket:T001")).toBeInTheDocument();
  });

  it("shows — for null detail_json", async () => {
    localStorage.setItem("staff_jwt", fakeJwt("engineer"));
    vi.mocked(listAudit).mockResolvedValue(MOCK_ENTRIES);

    renderRoute();

    await waitFor(() => expect(screen.getByText("alice")).toBeInTheDocument());
    // charlie's row has null detail — should show em-dash
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThan(0);
  });

  it("shows error alert on API failure", async () => {
    localStorage.setItem("staff_jwt", fakeJwt("engineer"));
    vi.mocked(listAudit).mockRejectedValue(new Error("network error"));

    renderRoute();

    await waitFor(() =>
      expect(screen.getByText("加载失败，请重试")).toBeInTheDocument(),
    );
  });

  it("refresh button calls listAudit again", async () => {
    localStorage.setItem("staff_jwt", fakeJwt("engineer"));
    vi.mocked(listAudit).mockResolvedValue(MOCK_ENTRIES);

    renderRoute();
    await waitFor(() => expect(screen.getByText("alice")).toBeInTheDocument());

    const refreshBtn = screen.getByRole("button", { name: /刷新/ });
    fireEvent.click(refreshBtn);

    await waitFor(() => expect(vi.mocked(listAudit).mock.calls.length).toBeGreaterThan(1));
  });

  it("renders column headers", async () => {
    localStorage.setItem("staff_jwt", fakeJwt("engineer"));
    vi.mocked(listAudit).mockResolvedValue([]);

    renderRoute();

    // antd Table 加 scroll={{x}} 后表头会渲染两份（measure + visible），
    // 用 getAllByText 取至少一次即可。
    await waitFor(() => expect(screen.getAllByText("时间").length).toBeGreaterThan(0));
    expect(screen.getAllByText("操作人").length).toBeGreaterThan(0);
    expect(screen.getAllByText("动作").length).toBeGreaterThan(0);
    expect(screen.getAllByText("对象").length).toBeGreaterThan(0);
    expect(screen.getAllByText("详情").length).toBeGreaterThan(0);
  });

  it("shows empty state message when no data", async () => {
    localStorage.setItem("staff_jwt", fakeJwt("engineer"));
    vi.mocked(listAudit).mockResolvedValue([]);

    renderRoute();

    await waitFor(() =>
      expect(screen.getByText("暂无审计记录")).toBeInTheDocument(),
    );
  });
});
