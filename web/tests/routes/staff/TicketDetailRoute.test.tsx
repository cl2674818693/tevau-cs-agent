// TicketDetailRoute：工单详情（概览 / 事件流 / 关联会话三 tab）。
// 用例：
//  1) 默认加载：渲染严重度 / 创建时间 / payload 字段
//  2) 404：Alert 工单加载失败
//  3) 事件流：events 渲染卡片
//  4) 关联会话：链接到 /staff/conversations/{id}/logs
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
          { event: "created", actor: "alice", comment: "新建", created_at: "2026-01-01 00:00:00" },
        ],
      }),
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

  it("关联会话：链接到 /staff/conversations/{id}/logs", async () => {
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
    renderWithRouter(<TicketDetailRoute />, {
      initialPath: "/staff/tickets/TIK-2",
      path: "/staff/tickets/:externalId",
    });
    const link = await screen.findByText("#314");
    expect(link.closest("a")).toHaveAttribute("href", "/staff/conversations/314/logs");
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
