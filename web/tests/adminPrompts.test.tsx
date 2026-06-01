import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { App as AntdApp, ConfigProvider } from "antd";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getPromptVersions, setRollout } from "../src/api/admin";
import { PromptsRoute } from "../src/routes/admin/PromptsRoute";

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

describe("admin api", () => {
  it("getPromptVersions fetches versions", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({ versions: ["v1.0.0", "v1.1.0"], default: "v1.1.0", rollout: {} }),
            { status: 200 },
          ),
      ),
    );
    const d = await getPromptVersions("t");
    expect(d.versions).toContain("v1.1.0");
  });

  it("setRollout posts rollout and returns new value", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ ok: true, rollout: { "v1.1.0": 50, "v1.0.0": 50 } }), {
            status: 200,
          }),
      ),
    );
    const out = await setRollout("t", { "v1.1.0": 50, "v1.0.0": 50 });
    expect(out["v1.0.0"]).toBe(50);
  });

  it("setRollout throws backend detail on 400", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ detail: "sum>100" }), { status: 400 })),
    );
    await expect(setRollout("t", { "v1.1.0": 80, "v1.0.0": 80 })).rejects.toThrow("sum>100");
  });
});

describe("PromptsRoute", () => {
  function renderRoute() {
    return render(
      <ConfigProvider>
        <AntdApp>
          <MemoryRouter initialEntries={["/admin/prompts"]}>
            <Routes>
              <Route path="/admin/prompts" element={<PromptsRoute />} />
            </Routes>
          </MemoryRouter>
        </AntdApp>
      </ConfigProvider>,
    );
  }

  it("blocks non-admin", async () => {
    localStorage.setItem("staff_jwt", fakeJwt("agent"));
    renderRoute();
    await waitFor(() => expect(screen.getByText("需要 admin 权限")).toBeTruthy());
  });

  it("loads versions and saves rollout via Sheet", async () => {
    localStorage.setItem("staff_jwt", fakeJwt("admin"));
    // 按 URL 分发，避免依赖调用顺序（PromptsRoute 挂载时还会拉 ab-stats）
    const fetchMock = vi.fn(async (url: string) => {
      if (url.includes("/prompts/ab-stats")) {
        return new Response(JSON.stringify({ versions: [] }), { status: 200 });
      }
      if (url.includes("/prompts/rollout")) {
        return new Response(JSON.stringify({ ok: true, rollout: { "v1.1.0": 100 } }), {
          status: 200,
        });
      }
      return new Response(
        JSON.stringify({
          versions: ["v1.0.0", "v1.1.0"],
          default: "v1.1.0",
          rollout: { "v1.1.0": 100 },
        }),
        { status: 200 },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    const { container } = renderRoute();
    // 等版本行出现
    await screen.findByText("v1.1.0");
    // 表格里的"调整流量" Button
    const editBtn = await screen.findByText("调整流量");
    fireEvent.click(editBtn);
    // Drawer Portal 默认渲染到 document.body 外、动画完成才显示，增大 waitFor 容忍
    await waitFor(
      () => expect(screen.queryByText(/调整流量 —/)).toBeInTheDocument(),
      { timeout: 3000 },
    );
    // 直接 submit form 绕过按钮位置不确定（Drawer body 内 Form htmlType=submit）
    const forms = container.ownerDocument.querySelectorAll("form");
    const drawerForm = forms[forms.length - 1];
    fireEvent.submit(drawerForm);
    await waitFor(() => expect(screen.getByText("已保存并热加载")).toBeTruthy());
  });
});
