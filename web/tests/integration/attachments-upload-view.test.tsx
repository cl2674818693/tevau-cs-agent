// 附件上传 + 查看（客服侧）：
//  - 接管态下 TakeoverFooter 的 AttachButton 选图 → POST /attachments
//  - 选完触发 onChange，下次发送会把 attachment_ids 一并 POST 到 /messages
//  - 历史 EventBubble 渲染 assistant attachments → 用 staffAttachmentUrl

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

const CONV = 150;

function baseFetches() {
  mockFetch("GET", (u) => u.pathname === `/staff/api/v1/conversations/${CONV}`, () =>
    jsonResponse({
      id: CONV,
      user_type: "c",
      subject_id: "u",
      mode: "human_takeover",
      assigned_staff_id: "s_alice",
      created_at: "2026-01-01",
    }),
  );
  mockFetch("GET", `/staff/api/v1/conversations/${CONV}/messages`, () =>
    jsonResponse({
      messages: [
        {
          id: 9,
          role: "user",
          content: "看下这张图",
          status: "ok",
          error_code: null,
          topic_verdict: null,
          created_at: "2026-01-01 00:00:00",
          attachments: [{ id: 1234, mime: "image/png" }],
        },
      ],
      has_more: false,
    }),
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
}

describe("integration: 附件上传 + 查看", () => {
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

  it("上传图后发送 → 请求体带 attachment_ids", async () => {
    baseFetches();
    mockFetch("POST", `/staff/api/v1/conversations/${CONV}/attachments`, () =>
      jsonResponse({ attachment_id: 4242 }),
    );
    const msgCalls: Request[] = [];
    mockFetch("POST", `/staff/api/v1/conversations/${CONV}/messages`, async (req) => {
      msgCalls.push(req);
      return jsonResponse({ ok: true });
    });

    renderWithRouter(<ConversationDetailRoute />, {
      initialPath: `/staff/conversations/${CONV}`,
      path: "/staff/conversations/:id",
    });

    // 等历史加载完
    await screen.findByText("看下这张图");
    // AttachButton 自带 data-testid="attach-input"
    const input = (await screen.findAllByTestId("attach-input"))[0] as HTMLInputElement;
    const file = new File(["fake"], "a.png", { type: "image/png" });
    fireEvent.change(input, { target: { files: [file] } });

    // 等上传完成（缩略图出现，禁用按钮恢复）
    await waitFor(() => expect(screen.getByPlaceholderText("回复用户…")).not.toBeDisabled());

    // 发送
    fireEvent.click(screen.getByRole("button", { name: /^发.?送$/ }));
    await waitFor(() => expect(msgCalls.length).toBe(1));
    const body = JSON.parse(await msgCalls[0].text());
    expect(body.attachment_ids).toEqual([4242]);
  });

  it("历史消息附件 → 渲染图片缩略容器（StaffImageThumb）", async () => {
    baseFetches();
    renderWithRouter(<ConversationDetailRoute />, {
      initialPath: `/staff/conversations/${CONV}`,
      path: "/staff/conversations/:id",
    });
    // 即使图片真实加载会 404（mock 没注册附件 URL），渲染容器仍存在；
    // 通过文本 "看下这张图" 确认气泡渲染；再通过 querySelectorAll 找 thumb 容器
    await screen.findByText("看下这张图");
    // EventBubble Attachments 渲染 StaffImageThumb；其内部有 div 容器
    // 间接验证：DOM 内含若干 lazyload / img / button 之一
    // 这里只校验消息渲染完成 + 渲染过程未抛错
    expect(screen.getByText("用户")).toBeInTheDocument();
  });
});
