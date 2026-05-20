import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
      <MemoryRouter initialEntries={["/admin/prompts"]}>
        <Routes>
          <Route path="/admin/prompts" element={<PromptsRoute />} />
        </Routes>
      </MemoryRouter>,
    );
  }

  it("blocks non-admin", async () => {
    localStorage.setItem("staff_jwt", fakeJwt("agent"));
    renderRoute();
    await waitFor(() => expect(screen.getByText("需要 admin 权限")).toBeTruthy());
  });

  it("loads versions and saves rollout", async () => {
    localStorage.setItem("staff_jwt", fakeJwt("admin"));
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            versions: ["v1.0.0", "v1.1.0"],
            default: "v1.1.0",
            rollout: { "v1.1.0": 100 },
          }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ok: true, rollout: { "v1.1.0": 100 } }), { status: 200 }),
      );
    vi.stubGlobal("fetch", fetchMock);

    renderRoute();
    await waitFor(() => expect(screen.getByText("v1.1.0")).toBeTruthy());
    fireEvent.click(screen.getByText("保存"));
    await waitFor(() => expect(screen.getByText("已保存并热加载")).toBeTruthy());
  });
});
