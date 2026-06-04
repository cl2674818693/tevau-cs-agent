// TicketDetailRoute：工单详情（概览 / 事件流 / 关联会话三 tab）。
// 用例：
//  1) 默认加载：渲染严重度 / 创建时间 / payload 字段
//  2) 404：Alert 工单加载失败
//  3) 事件流：events 渲染卡片
//  4) 关联会话：内联渲染会话消息 + "查看完整日志"链接到 logs 页
//  5) payload_json 非法 → fallback 空对象，仍不崩

import { screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TicketDetailRoute } from "@/routes/staff/TicketDetailRoute";

import {
  installFetch,
  jsonResponse,
  mockFetch,
  resetFetch,
} from "../../helpers/fetchMock";
import { renderWithRouter } from "../../helpers/render";
import { loginAsStaff, logoutStaff } from "../../helpers/session";

describe("TicketDetailRoute", () => {
  beforeEach(() => {
    installFetch();
    loginAsStaff("s_alice", "agent");
  });
  afterEach(() => {
    resetFetch();
    logoutStaff();
    vi.restoreAllMocks();
  });

  it("默认加载：概览渲染严重度 + payload 字段", async () => {
    mockFetch("GET", "/staff/api/v1/tickets/TIK-1", () =>
      jsonResponse({
        external_id: "TIK-1",
        conversation_id: 200,
        payload_json: JSON.stringify({ summary: "卡被锁", source: "AI" }),
        current_severity: "P1",
        created_at: "2026-01-01 00:00:00",
        events: [
          {
            event: "created",
            actor: "alice",
            comment: "新建",
            raw_json: null,
            created_at: "2026-01-01 00:00:00",
          },
        ],
      }),
    );
    // forceRender=true 让"关联会话"tab 也立即拉消息，给个空回包
    mockFetch("GET", "/staff/api/v1/conversations/200/messages", () =>
      jsonResponse({ messages: [], has_more: false }),
    );
    renderWithRouter(<TicketDetailRoute />, {
      initialPath: "/staff/tickets/TIK-1",
      path: "/staff/tickets/:externalId",
    });
    expect(await screen.findByText("工单 — TIK-1")).toBeInTheDocument();
    expect(screen.getByText("P1")).toBeInTheDocument();
    // payload 字段（key + value）
    expect(screen.getByText("summary")).toBeInTheDocument();
    expect(screen.getByText("卡被锁")).toBeInTheDocument();
    // forceRender=true 让事件流也渲染了
    expect(screen.getByText("created")).toBeInTheDocument();
  });

  it("404 → Alert 工单加载失败", async () => {
    mockFetch("GET", "/staff/api/v1/tickets/MISS", () => new Response("", { status: 404 }));
    renderWithRouter(<TicketDetailRoute />, {
      initialPath: "/staff/tickets/MISS",
      path: "/staff/tickets/:externalId",
    });
    expect(await screen.findByText("工单加载失败")).toBeInTheDocument();
  });

  it("关联会话：内联渲染消息 + 顶部'查看完整日志'链接到 logs 页", async () => {
    mockFetch("GET", "/staff/api/v1/tickets/TIK-2", () =>
      jsonResponse({
        external_id: "TIK-2",
        conversation_id: 314,
        payload_json: "{}",
        current_severity: null,
        created_at: "2026-01-01 00:00:00",
        events: [],
      }),
    );
    mockFetch("GET", "/staff/api/v1/conversations/314/messages", () =>
      jsonResponse({
        messages: [
          {
            id: 1,
            role: "user",
            content: "卡被冻结了",
            status: "ok",
            error_code: null,
            topic_verdict: null,
            created_at: "2026-01-01 00:00:00",
          },
          {
            id: 2,
            role: "assistant",
            content: "已为您建工单",
            status: "ok",
            error_code: null,
            topic_verdict: null,
            created_at: "2026-01-01 00:00:01",
          },
        ],
        has_more: false,
      }),
    );
    renderWithRouter(<TicketDetailRoute />, {
      initialPath: "/staff/tickets/TIK-2",
      path: "/staff/tickets/:externalId",
    });
    // 内联消息内容直接可见，不需要再点会话 ID 跳转
    expect(await screen.findByText("卡被冻结了")).toBeInTheDocument();
    expect(screen.getByText("已为您建工单")).toBeInTheDocument();
    // 顶部"查看完整日志"仍然链接到 logs 页，方便看更全
    const link = screen.getByText("查看完整日志");
    expect(link.closest("a")).toHaveAttribute("href", "/staff/conversations/314/logs");
  });

  it("evidence_added 事件：raw_json 里的新 evidence 在事件流 tab 渲染 + 概览顶部出现追加次数告警", async () => {
    mockFetch("GET", "/staff/api/v1/tickets/TIK-APPEND", () =>
      jsonResponse({
        external_id: "TIK-APPEND",
        conversation_id: 555,
        payload_json: JSON.stringify({ summary: "首次卡冻结", evidence: { card_number_masked: "446614******7494" } }),
        current_severity: "P2",
        created_at: "2026-01-01 00:00:00",
        events: [
          {
            event: "evidence_added",
            actor: "ai",
            comment: "用户申请第二张卡解冻",
            raw_json: JSON.stringify({
              category: "人工介入",
              severity: "p2",
              evidence: { card_number: "4466148010697494", user_request: "卡被冻结，申请解锁" },
            }),
            created_at: "2026-01-01 00:30:00",
          },
        ],
      }),
    );
    mockFetch("GET", "/staff/api/v1/conversations/555/messages", () =>
      jsonResponse({ messages: [], has_more: false }),
    );
    renderWithRouter(<TicketDetailRoute />, {
      initialPath: "/staff/tickets/TIK-APPEND",
      path: "/staff/tickets/:externalId",
    });
    expect(await screen.findByText("工单 — TIK-APPEND")).toBeInTheDocument();
    // 概览顶部出现追加次数告警
    expect(
      screen.getByText(/本工单已被追加 1 次证据/),
    ).toBeInTheDocument();
    // 事件流（forceRender=true 已挂载）：分类 / 严重度 / 新 evidence 都渲染
    expect(screen.getByText(/分类：人工介入/)).toBeInTheDocument();
    expect(screen.getByText(/严重度：p2/)).toBeInTheDocument();
    expect(screen.getByText(/4466148010697494/)).toBeInTheDocument();
  });

  it("payload_json 非法 JSON → fallback 空对象，不崩", async () => {
    mockFetch("GET", "/staff/api/v1/tickets/TIK-3", () =>
      jsonResponse({
        external_id: "TIK-3",
        conversation_id: 999,
        payload_json: "this is not json",
        current_severity: null,
        created_at: "2026-01-01 00:00:00",
        events: [],
      }),
    );
    mockFetch("GET", "/staff/api/v1/conversations/999/messages", () =>
      jsonResponse({ messages: [], has_more: false }),
    );
    renderWithRouter(<TicketDetailRoute />, {
      initialPath: "/staff/tickets/TIK-3",
      path: "/staff/tickets/:externalId",
    });
    expect(await screen.findByText("工单 — TIK-3")).toBeInTheDocument();
    // 退化为 ["payload", "（空）"] 行
    expect(screen.getByText("payload")).toBeInTheDocument();
    expect(screen.getByText("（空）")).toBeInTheDocument();
  });
});
