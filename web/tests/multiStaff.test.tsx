import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getKpi, resolveConversation, transferConversation } from "../src/api/staff";
import { TakeoverFooter } from "../src/components/TakeoverFooter";
import { KpiRoute } from "../src/routes/staff/KpiRoute";

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

describe("staff api transfer/resolve/kpi", () => {
  it("transferConversation posts to transfer-to", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("{}", { status: 200 })),
    );
    const ok = await transferConversation("t", 3, "EN1");
    expect(ok).toBe(true);
    expect((fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe(
      "/staff/api/v1/conversations/3/transfer-to/EN1",
    );
  });

  it("resolveConversation posts to resolve", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("{}", { status: 200 })),
    );
    await resolveConversation("t", 3);
    expect((fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe(
      "/staff/api/v1/conversations/3/resolve",
    );
  });

  it("getKpi returns staff array", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ staff: [{ staff_id: "AG1", takeovers: 2 }] }), {
            status: 200,
          }),
      ),
    );
    const res = await getKpi("t");
    expect(res.staff[0].staff_id).toBe("AG1");
  });
});

describe("KpiRoute", () => {
  it("renders kpi cards for current user", async () => {
    // JWT: { role: "agent", sub: "AG1" }
    localStorage.setItem("staff_jwt", `h.${btoa(JSON.stringify({ role: "agent", sub: "AG1" }))}.s`);
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              staff: [
                {
                  staff_id: "AG1",
                  takeovers: 4,
                  releases: 1,
                  resolved: 3,
                  release_ratio: 0.25,
                  resolved_ratio: 0.75,
                  avg_handle_seconds: 125,
                },
              ],
            }),
            { status: 200 },
          ),
      ),
    );
    render(
      <MemoryRouter initialEntries={["/staff/kpi"]}>
        <Routes>
          <Route path="/staff/kpi" element={<KpiRoute />} />
        </Routes>
      </MemoryRouter>,
    );
    // 接管数
    await waitFor(() => expect(screen.getByText("4")).toBeTruthy());
    // 解决数
    expect(screen.getByText("3")).toBeTruthy();
    // 平均时长
    expect(screen.getByText("2分5秒")).toBeTruthy();
  });
});

describe("TakeoverFooter", () => {
  it("transfer calls api and notifies", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("{}", { status: 200 })),
    );
    const onNotice = vi.fn();
    render(<TakeoverFooter token="t" convId={5} onNotice={onNotice} />);
    fireEvent.change(screen.getByPlaceholderText("转派给 staff_id…"), {
      target: { value: "EN1" },
    });
    fireEvent.click(screen.getByText("转派"));
    await waitFor(() => expect(onNotice).toHaveBeenCalledWith("已转派给 EN1"));
  });

  it("resolve calls api and notifies", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("{}", { status: 200 })),
    );
    const onNotice = vi.fn();
    render(<TakeoverFooter token="t" convId={5} onNotice={onNotice} />);
    fireEvent.click(screen.getByText("标记已解决"));
    await waitFor(() => expect(onNotice).toHaveBeenCalledWith("已标记解决并释放回 AI"));
  });
});
