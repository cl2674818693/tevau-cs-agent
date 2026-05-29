import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getConversationMessages, getKnowledgeGaps, getRecentAudits } from "../src/api/staff";
import { AuditsRoute } from "../src/routes/staff/AuditsRoute";
import { ConversationLogsRoute } from "../src/routes/staff/ConversationLogsRoute";
import { InsightsRoute } from "../src/routes/staff/InsightsRoute";

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

describe("api/staff 留痕 fetchers", () => {
  it("getKnowledgeGaps returns counts", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => json({ out_of_scope: 2, failed_turns: 1, thumbs_down: 3 })),
    );
    const g = await getKnowledgeGaps("t");
    expect(g.out_of_scope).toBe(2);
    expect(g.thumbs_down).toBe(3);
  });

  it("getConversationMessages unwraps messages array", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => json({ conversation_id: 1, messages: [{ id: 5, role: "user" }] })),
    );
    const m = await getConversationMessages("t", 1);
    expect(m.messages[0].id).toBe(5);
  });

  it("getRecentAudits sets rejected query param", async () => {
    const f = vi.fn(async (_url: string, _opts?: RequestInit) => json({ audits: [] }));
    vi.stubGlobal("fetch", f);
    await getRecentAudits("t", { rejectedOnly: true });
    expect(f.mock.calls[0][0]).toContain("rejected=true");
  });
});

describe("InsightsRoute", () => {
  it("renders the three gap counts", async () => {
    localStorage.setItem("staff_jwt", "t");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => json({ out_of_scope: 7, failed_turns: 4, thumbs_down: 9 })),
    );
    render(
      <MemoryRouter>
        <InsightsRoute />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("7")).toBeTruthy());
    expect(screen.getByText("范围外")).toBeTruthy();
  });
});

describe("AuditsRoute", () => {
  it("renders a rejected audit row", async () => {
    localStorage.setItem("staff_jwt", "t");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        json({
          audits: [
            {
              id: 1,
              conversation_id: 3,
              tool_name: "query_user",
              params_json: "{}",
              result_size: 0,
              duration_ms: 5,
              rejected: 1,
              reject_reason: "越权被拒",
              created_at: "2026-05-25 10:00:00",
            },
          ],
        }),
      ),
    );
    render(
      <MemoryRouter>
        <AuditsRoute />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText(/越权被拒/)).toBeTruthy());
  });
});

describe("ConversationLogsRoute", () => {
  it("renders message history with failed badge", async () => {
    localStorage.setItem("staff_jwt", "t");
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.includes("/messages"))
          return json({
            messages: [
              {
                id: 1,
                role: "user",
                content: "问题",
                status: "failed",
                error_code: "INTERNAL_ERROR",
                topic_verdict: "no",
                created_at: "t",
              },
            ],
          });
        if (url.includes("/tool-audits")) return json({ audits: [] });
        return json({ feedback: [] });
      }),
    );
    render(
      <MemoryRouter initialEntries={["/staff/conversations/3/logs"]}>
        <Routes>
          <Route path="/staff/conversations/:id/logs" element={<ConversationLogsRoute />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText(/INTERNAL_ERROR/)).toBeTruthy());
    expect(screen.getByText(/verdict:no/)).toBeTruthy();
  });
});
