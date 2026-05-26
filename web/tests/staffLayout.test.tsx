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

  // 响应式：导航项同时存在于桌面侧栏与移动端底部 Tab（CSS 断点切换显示），
  // 故 jsdom 中每个导航标签出现 >1 次，用 getAllByText 断言存在。
  it("有 token 时渲染导航与内容；非 admin 不显示 Prompt 灰度", () => {
    localStorage.setItem("staff_jwt", fakeJwt("agent"));
    renderShell();
    expect(screen.getByText("列表内容")).toBeTruthy();
    expect(screen.getAllByText("工单").length).toBeGreaterThan(0);
    expect(screen.getAllByText("KPI").length).toBeGreaterThan(0);
    expect(screen.queryByText("Prompt 灰度")).toBeNull();
  });

  it("admin 显示 Prompt 灰度入口", () => {
    localStorage.setItem("staff_jwt", fakeJwt("admin"));
    renderShell();
    expect(screen.getAllByText("Prompt 灰度").length).toBeGreaterThan(0);
  });

  it("点击退出清除 token", () => {
    localStorage.setItem("staff_jwt", fakeJwt("agent"));
    renderShell();
    fireEvent.click(screen.getAllByText("退出")[0]);
    expect(localStorage.getItem("staff_jwt")).toBeNull();
  });
});
