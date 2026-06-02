// 401 重登剧本：staffFetch 收到 401 → clearStaffToken + window.location.href = /staff/login。
// 用例覆盖：
//  - 401 触发 location.href 跳转
//  - 已在 /staff/login 路径下时不重复跳，避免冲掉错误提示
//  - 401 后 localStorage 的 staff_jwt 被清

import { render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App as AntdApp, ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ConversationsListRoute } from "@/routes/staff/ConversationsListRoute";

import { installFetch, mockFetch, resetFetch } from "../helpers/fetchMock";
import { loginAsStaff, logoutStaff } from "../helpers/session";

let _origLocation: Location | null = null;
function spyHref(pathname: string) {
  const spy = vi.fn();
  if (_origLocation === null) _origLocation = window.location;
  Object.defineProperty(window, "location", {
    writable: true,
    configurable: true,
    value: {
      ..._origLocation,
      pathname,
      get href() {
        return _origLocation!.href;
      },
      set href(v: string) {
        spy(v);
      },
    },
  });
  return spy;
}
function restoreHref() {
  if (_origLocation) {
    Object.defineProperty(window, "location", {
      writable: true,
      configurable: true,
      value: _origLocation,
    });
    _origLocation = null;
  }
}

function renderList() {
  return render(
    <ConfigProvider locale={zhCN}>
      <AntdApp>
        <MemoryRouter initialEntries={["/staff/conversations"]}>
          <Routes>
            <Route path="/staff/conversations" element={<ConversationsListRoute />} />
          </Routes>
        </MemoryRouter>
      </AntdApp>
    </ConfigProvider>,
  );
}

describe("integration: 401 relogin", () => {
  beforeEach(() => {
    installFetch();
    loginAsStaff("s_alice", "agent");
  });
  afterEach(() => {
    resetFetch();
    logoutStaff();
    restoreHref();
    vi.restoreAllMocks();
  });

  it("staff 接口 401 → 跳 /staff/login + 清 token", async () => {
    const hrefSpy = spyHref("/staff/conversations");
    mockFetch("GET", "/staff/api/v1/conversations", () => new Response("", { status: 401 }));
    renderList();
    await waitFor(() => expect(hrefSpy).toHaveBeenCalledWith("/staff/login"));
    expect(localStorage.getItem("staff_jwt")).toBeNull();
  });

  it("已在 /staff/login 路径下 → 401 不再重复跳", async () => {
    const hrefSpy = spyHref("/staff/login");
    mockFetch("GET", "/staff/api/v1/conversations", () => new Response("", { status: 401 }));
    renderList();
    // 等几毫秒让 fetch 跑完
    await new Promise((r) => setTimeout(r, 30));
    expect(hrefSpy).not.toHaveBeenCalled();
  });
});
