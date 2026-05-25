import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { StaffLayout } from "../src/components/StaffLayout";

function fakeJwt(role: string): string {
  return `h.${btoa(JSON.stringify({ role, sub: "AD1" }))}.s`;
}

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

function renderShell(entry = "/staff/conversations") {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route element={<StaffLayout />}>
          <Route path="/staff/conversations" element={<div>列表内容</div>} />
          <Route path="/staff/kpi" element={<div>KPI内容</div>} />
          <Route path="/admin/prompts" element={<div>Prompt内容</div>} />
        </Route>
        <Route path="/staff/login" element={<div>登录页占位</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("StaffLayout", () => {
  it("无 token 时重定向到登录页", () => {
    renderShell();
    expect(screen.getByText("登录页占位")).toBeTruthy();
    expect(screen.queryByText("列表内容")).toBeNull();
  });

  it("有 token 时渲染侧栏与内容；非 admin 不显示 Prompt 灰度", () => {
    localStorage.setItem("staff_jwt", fakeJwt("agent"));
    renderShell();
    expect(screen.getByText("列表内容")).toBeTruthy();
    expect(screen.getByText("工单")).toBeTruthy();
    expect(screen.getByText("KPI")).toBeTruthy();
    expect(screen.queryByText("Prompt 灰度")).toBeNull();
  });

  it("admin 显示 Prompt 灰度入口", () => {
    localStorage.setItem("staff_jwt", fakeJwt("admin"));
    renderShell();
    expect(screen.getByText("Prompt 灰度")).toBeTruthy();
  });

  it("点击退出清除 token", () => {
    localStorage.setItem("staff_jwt", fakeJwt("agent"));
    renderShell();
    fireEvent.click(screen.getByText("退出"));
    expect(localStorage.getItem("staff_jwt")).toBeNull();
  });
});
