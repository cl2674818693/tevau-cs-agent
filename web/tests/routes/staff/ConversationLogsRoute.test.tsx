// ConversationLogsRoute：会话留痕（消息流 + 工具调用 + 反馈三标签页）。
// 测试矩阵：
//  1) 默认加载：默认 messages tab 显示消息气泡
//  2) 错误态：messages 接口 500 → Alert
//  3) 空消息：显示「无消息记录」
//  4) "加载更早" 按钮：hasMore=true 出现，点击带 before_id
//  5) audits / feedback 通过另一个并发请求拉取
//  6) 切到 audits tab：渲染审计行；空时显示「无工具调用记录」
//  7) 切到 feedback tab：渲染 👍/👎
//  8) 切到 audits tab 显示 ExpandableText 长 params 截断

import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ConversationLogsRoute } from "@/routes/staff/ConversationLogsRoute";

import {
  installFetch,
  jsonResponse,
  mockFetch,
  resetFetch,
} from "../../helpers/fetchMock";
import { renderWithRouter } from "../../helpers/render";
import { loginAsStaff, logoutStaff } from "../../helpers/session";

const CONV_ID = 50;

function setupAuditsFeedback(opts: {
  audits?: unknown[];
  feedback?: unknown[];
} = {}) {
  mockFetch("GET", `/staff/api/v1/conversations/${CONV_ID}/tool-audits`, () =>
    jsonResponse({ audits: opts.audits ?? [] }),
  );
  mockFetch("GET", `/staff/api/v1/conversations/${CONV_ID}/feedback`, () =>
    jsonResponse({ feedback: opts.feedback ?? [] }),
  );
}

describe("ConversationLogsRoute", () => {
  beforeEach(() => {
    installFetch();
    loginAsStaff("s_alice", "agent");
  });
  afterEach(() => {
    resetFetch();
    logoutStaff();
    vi.restoreAllMocks();
  });

  it("默认加载：消息 tab 渲染气泡 + 时间戳", async () => {
    mockFetch("GET", `/staff/api/v1/conversations/${CONV_ID}/messages`, () =>
      jsonResponse({
        messages: [
          {
            id: 11,
            role: "user",
            content: "查一下我的卡",
            status: "ok",
            error_code: null,
            topic_verdict: null,
            created_at: "2026-01-01 00:00:00",
          },
          {
            id: 12,
            role: "assistant",
            content: "请提供卡号后四位",
            status: "ok",
            error_code: null,
            topic_verdict: null,
            created_at: "2026-01-01 00:00:01",
          },
        ],
        has_more: false,
      }),
    );
    setupAuditsFeedback();

    renderWithRouter(<ConversationLogsRoute />, {
      initialPath: `/staff/conversations/${CONV_ID}/logs`,
      path: "/staff/conversations/:id/logs",
    });

    expect(await screen.findByText("查一下我的卡")).toBeInTheDocument();
    expect(screen.getByText("请提供卡号后四位")).toBeInTheDocument();
    expect(screen.getByText("2026-01-01 00:00:00")).toBeInTheDocument();
  });

  it("消息接口 500 → Alert 加载失败", async () => {
    mockFetch("GET", `/staff/api/v1/conversations/${CONV_ID}/messages`, () =>
      new Response("", { status: 500 }),
    );
    setupAuditsFeedback();
    renderWithRouter(<ConversationLogsRoute />, {
      initialPath: `/staff/conversations/${CONV_ID}/logs`,
      path: "/staff/conversations/:id/logs",
    });
    expect(await screen.findByText("加载失败")).toBeInTheDocument();
  });

  it("空消息 → 「无消息记录」", async () => {
    mockFetch("GET", `/staff/api/v1/conversations/${CONV_ID}/messages`, () =>
      jsonResponse({ messages: [], has_more: false }),
    );
    setupAuditsFeedback();
    renderWithRouter(<ConversationLogsRoute />, {
      initialPath: `/staff/conversations/${CONV_ID}/logs`,
      path: "/staff/conversations/:id/logs",
    });
    expect(await screen.findByText("无消息记录")).toBeInTheDocument();
  });

  it("hasMore=true → 「加载更早消息」按钮存在；点击带 before_id", async () => {
    let firstCall = true;
    const urls: string[] = [];
    mockFetch("GET", `/staff/api/v1/conversations/${CONV_ID}/messages`, (req) => {
      urls.push(req.url);
      if (firstCall) {
        firstCall = false;
        return jsonResponse({
          messages: [
            {
              id: 100,
              role: "user",
              content: "first",
              status: "ok",
              error_code: null,
              topic_verdict: null,
              created_at: "2026-01-01 00:00:00",
            },
          ],
          has_more: true,
        });
      }
      return jsonResponse({ messages: [], has_more: false });
    });
    setupAuditsFeedback();

    renderWithRouter(<ConversationLogsRoute />, {
      initialPath: `/staff/conversations/${CONV_ID}/logs`,
      path: "/staff/conversations/:id/logs",
    });

    const btn = await screen.findByRole("button", { name: /加载更早消息/ });
    fireEvent.click(btn);
    await waitFor(() => expect(urls.length).toBe(2));
    expect(urls[1]).toContain("before_id=100");
  });

  it("切到 audits tab → 渲染工具调用行", async () => {
    mockFetch("GET", `/staff/api/v1/conversations/${CONV_ID}/messages`, () =>
      jsonResponse({ messages: [], has_more: false }),
    );
    setupAuditsFeedback({
      audits: [
        {
          id: 1,
          tool_name: "query_user",
          params_json: '{"user_id": 1}',
          result_size: 100,
          duration_ms: 42,
          rejected: 0,
          reject_reason: null,
          created_at: "2026-01-01 00:00:00",
          result_count: 1,
          is_empty: 0,
          subject_id: "u_alpha",
          user_type: "c",
        },
      ],
    });

    renderWithRouter(<ConversationLogsRoute />, {
      initialPath: `/staff/conversations/${CONV_ID}/logs`,
      path: "/staff/conversations/:id/logs",
    });

    fireEvent.click(await screen.findByRole("tab", { name: /工具调用/ }));
    expect(await screen.findByText("query_user")).toBeInTheDocument();
    expect(screen.getByText("通过")).toBeInTheDocument();
    expect(screen.getByText(/42ms/)).toBeInTheDocument();
  });

  it("切到 feedback tab → 渲染 👍/👎 反馈", async () => {
    mockFetch("GET", `/staff/api/v1/conversations/${CONV_ID}/messages`, () =>
      jsonResponse({ messages: [], has_more: false }),
    );
    setupAuditsFeedback({
      feedback: [
        { id: 1, message_id: 7, rating: "up", reason: null, created_at: "2026-01-01 00:00:00" },
        { id: 2, message_id: 9, rating: "down", reason: "不准", created_at: "2026-01-01 00:00:01" },
      ],
    });

    renderWithRouter(<ConversationLogsRoute />, {
      initialPath: `/staff/conversations/${CONV_ID}/logs`,
      path: "/staff/conversations/:id/logs",
    });
    fireEvent.click(await screen.findByRole("tab", { name: /反馈/ }));
    expect(await screen.findByText("不准")).toBeInTheDocument();
    expect(screen.getByLabelText("thumbs up")).toBeInTheDocument();
    expect(screen.getByLabelText("thumbs down")).toBeInTheDocument();
  });

  it("audits 为空 → 显示「无工具调用记录」", async () => {
    mockFetch("GET", `/staff/api/v1/conversations/${CONV_ID}/messages`, () =>
      jsonResponse({ messages: [], has_more: false }),
    );
    setupAuditsFeedback({ audits: [] });
    renderWithRouter(<ConversationLogsRoute />, {
      initialPath: `/staff/conversations/${CONV_ID}/logs`,
      path: "/staff/conversations/:id/logs",
    });
    fireEvent.click(await screen.findByRole("tab", { name: /工具调用/ }));
    expect(await screen.findByText("无工具调用记录")).toBeInTheDocument();
  });
});
