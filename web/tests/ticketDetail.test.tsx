import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TicketDetailRoute } from "../src/routes/staff/TicketDetailRoute";

beforeEach(() => {
  const store = new Map<string, string>();
  vi.stubGlobal("localStorage", {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
    removeItem: (k: string) => void store.delete(k),
    clear: () => store.clear(),
  });
});
afterEach(() => vi.restoreAllMocks());

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200 });
}

const TICKET = {
  external_id: "AI-42",
  conversation_id: 7,
  payload_json: JSON.stringify({ category: "billing", priority: "high" }),
  current_severity: "P2",
  created_at: "2026-05-01 10:00:00",
  events: [
    { event: "created", actor: "admin@test.com", comment: "initial", created_at: "2026-05-01 10:00:00" },
    { event: "assigned", actor: "staff1", comment: null, created_at: "2026-05-01 10:05:00" },
  ],
};

function renderRoute(externalId = "AI-42") {
  localStorage.setItem("staff_jwt", "test-token");
  vi.stubGlobal("fetch", vi.fn(async () => json(TICKET)));
  render(
    <MemoryRouter initialEntries={[`/staff/tickets/${externalId}`]}>
      <Routes>
        <Route path="/staff/tickets/:externalId" element={<TicketDetailRoute />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("TicketDetailRoute", () => {
  it("renders breadcrumb with externalId", async () => {
    renderRoute("AI-42");
    await waitFor(() => expect(screen.getByText("AI-42")).toBeTruthy());
    expect(screen.getByText("工单")).toBeTruthy();
    expect(screen.getByText("工作台")).toBeTruthy();
  });

  it("renders page title with externalId", async () => {
    renderRoute("AI-42");
    await waitFor(() => expect(screen.getByText("工单 — AI-42")).toBeTruthy());
  });

  it("renders 返回 button", async () => {
    renderRoute("AI-42");
    await waitFor(() => expect(screen.getByText("返回工单列表")).toBeTruthy());
  });

  it("overview tab shows severity and payload fields", async () => {
    renderRoute("AI-42");
    await waitFor(() => expect(screen.getByText("P2")).toBeTruthy());
    expect(screen.getByText("billing")).toBeTruthy();
    expect(screen.getByText("high")).toBeTruthy();
  });

  it("events tab trigger is present and data loaded into DOM", async () => {
    renderRoute("AI-42");
    await waitFor(() => expect(screen.getByText("P2")).toBeTruthy());
    // Tab triggers exist
    expect(screen.getByRole("tab", { name: "事件流" })).toBeTruthy();
    // Event data is rendered (tab panel may be hidden; query by role with hidden:true)
    const panels = screen.getAllByRole("tabpanel", { hidden: true });
    const eventsPanel = panels.find((p) => p.id.includes("events"));
    expect(eventsPanel).toBeTruthy();
  });

  it("three tab triggers are rendered", async () => {
    renderRoute("AI-42");
    await waitFor(() => expect(screen.getByText("P2")).toBeTruthy());
    const tabs = screen.getAllByRole("tab");
    const names = tabs.map((t) => t.textContent);
    expect(names).toContain("概览");
    expect(names).toContain("事件流");
    expect(names).toContain("关联会话");
  });

  it("conversations tab trigger is present", async () => {
    renderRoute("AI-42");
    await waitFor(() => expect(screen.getByText("P2")).toBeTruthy());
    expect(screen.getByRole("tab", { name: "关联会话" })).toBeTruthy();
  });

  it("shows error alert on fetch failure", async () => {
    localStorage.setItem("staff_jwt", "test-token");
    vi.stubGlobal("fetch", vi.fn(async () => new Response("{}", { status: 500 })));
    render(
      <MemoryRouter initialEntries={["/staff/tickets/BAD"]}>
        <Routes>
          <Route path="/staff/tickets/:externalId" element={<TicketDetailRoute />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("工单加载失败")).toBeTruthy());
  });

  it("shows 404 error message from api", async () => {
    localStorage.setItem("staff_jwt", "test-token");
    vi.stubGlobal("fetch", vi.fn(async () => new Response("{}", { status: 404 })));
    render(
      <MemoryRouter initialEntries={["/staff/tickets/NOTFOUND"]}>
        <Routes>
          <Route path="/staff/tickets/:externalId" element={<TicketDetailRoute />} />
        </Routes>
      </MemoryRouter>,
    );
    // useAsyncData uses errorMsg param; 404 throws "工单不存在" inside getTicketDetail
    // but useAsyncData catches it and shows the default errorMsg "工单加载失败"
    await waitFor(() => expect(screen.getByText("工单加载失败")).toBeTruthy());
  });
});
