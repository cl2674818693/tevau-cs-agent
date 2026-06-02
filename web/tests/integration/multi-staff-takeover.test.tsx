// 多客服剧本：A 试图接管已被 B 接管的会话。
//  - 我（s_alice）打开会话，已显示「已被 s_bob 接管」disabled
//  - 后端推 release (mode_change to=ai) → 按钮变回「接管」可点
//  - 此时 s_alice 接管成功 → UI 变「释放回 AI」

import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { stream } = vi.hoisted(() => {
  const s = {
    q: [] as { value?: unknown; done?: boolean }[],
    waiters: [] as ((v: { value?: unknown; done?: boolean }) => void)[],
    push(ev: unknown) {
      if (this.waiters.length) this.waiters.shift()!({ value: ev });
      else this.q.push({ value: ev });
    },
    close() {
      const ws = this.waiters.splice(0);
      ws.forEach((w) => w({ done: true }));
    },
    reset() {
      this.q = [];
      this.waiters = [];
    },
    next(): Promise<{ value?: unknown; done?: boolean }> {
      if (this.q.length) return Promise.resolve(this.q.shift()!);
      return new Promise((r) => this.waiters.push(r));
    },
  };
  return { stream: s };
});
vi.mock("@/api/staff", async () => {
  const actual = await vi.importActual<typeof import("@/api/staff")>("@/api/staff");
  return {
    ...actual,
    streamStaffEvents: async function* () {
      for (;;) {
        const { value, done } = await stream.next();
        if (done) return;
        yield value as never;
      }
    },
  };
});

import { ConversationDetailRoute } from "@/routes/staff/ConversationDetailRoute";

import {
  installFetch,
  jsonResponse,
  mockFetch,
  resetFetch,
} from "../helpers/fetchMock";
import { renderWithRouter } from "../helpers/render";
import { loginAsStaff, logoutStaff } from "../helpers/session";

const CONV = 101;

describe("integration: 多客服接管", () => {
  beforeEach(() => {
    installFetch();
    loginAsStaff("s_alice", "agent");
    stream.reset();
  });
  afterEach(() => {
    stream.close();
    resetFetch();
    logoutStaff();
    stream.reset();
    vi.restoreAllMocks();
  });

  it("已被 s_bob 接管 → bob 释放 → alice 可接管成功", async () => {
    mockFetch("GET", (u) => u.pathname === `/staff/api/v1/conversations/${CONV}`, () =>
      jsonResponse({
        id: CONV,
        user_type: "c",
        subject_id: "u",
        mode: "human_takeover",
        assigned_staff_id: "s_bob",
        created_at: "2026-01-01",
      }),
    );
    mockFetch("GET", `/staff/api/v1/conversations/${CONV}/messages`, () =>
      jsonResponse({ messages: [], has_more: false }),
    );
    mockFetch("GET", `/staff/api/v1/conversations/${CONV}/subject-info`, () =>
      jsonResponse({
        subject: { user_type: "c", subject_id: "u", found: false },
        client_info: null,
      }),
    );
    mockFetch("GET", "/staff/api/v1/transfer-candidates", () =>
      jsonResponse({ candidates: [] }),
    );
    mockFetch("POST", `/staff/api/v1/conversations/${CONV}/take`, () =>
      jsonResponse({ ok: true }),
    );

    renderWithRouter(<ConversationDetailRoute />, {
      initialPath: `/staff/conversations/${CONV}`,
      path: "/staff/conversations/:id",
    });

    // 一开始按钮禁用
    expect(
      await screen.findByRole("button", { name: /已被 s_bob 接管/ }),
    ).toBeDisabled();

    // bob 释放 → 推 mode_change to=ai
    stream.push({ type: "mode_change", to: "ai" });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /^接.?管$/ })).toBeInTheDocument(),
    );

    // alice 接管
    fireEvent.click(screen.getByRole("button", { name: /^接.?管$/ }));
    expect(await screen.findByRole("button", { name: /释放回 AI/ })).toBeInTheDocument();
  });
});
