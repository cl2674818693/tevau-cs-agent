// ConversationInfoCard：会话元信息 + 风险标记 + 复制按钮（剪贴板降级）。
import { App as AntApp } from "antd";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ConversationInfoCard } from "@/components/ConversationInfoCard";
import type { StaffConversation } from "@/api/staff";

function wrap(ui: React.ReactNode) {
  return render(<AntApp>{ui}</AntApp>);
}

const BASE: StaffConversation = {
  id: 42,
  user_type: "c",
  subject_id: "u-abc",
  mode: "human_takeover",
  assigned_staff_id: "agent-1",
  assigned_at: new Date(Date.now() - 60_000).toISOString().replace("T", " ").replace(/\.\d+Z$/, ""),
  created_at: new Date(Date.now() - 600_000).toISOString().replace("T", " ").replace(/\.\d+Z$/, ""),
};

beforeEach(() => {
  // 重写 navigator.clipboard
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: vi.fn(async () => {}) },
  });
});
afterEach(() => vi.restoreAllMocks());

describe("ConversationInfoCard", () => {
  it("conv=null：显示占位 —", () => {
    wrap(<ConversationInfoCard conv={null} />);
    expect(screen.getByText("会话信息")).toBeInTheDocument();
  });

  it("渲染基础元信息（ID/Subject/客服）", () => {
    wrap(<ConversationInfoCard conv={BASE} />);
    expect(screen.getByText("#42")).toBeInTheDocument();
    expect(screen.getByText("u-abc")).toBeInTheDocument();
    expect(screen.getByText("agent-1")).toBeInTheDocument();
    expect(screen.getByText("C 端用户")).toBeInTheDocument();
  });

  it("mode 标签：human_takeover → 人工接管", () => {
    wrap(<ConversationInfoCard conv={BASE} />);
    expect(screen.getByText("人工接管")).toBeInTheDocument();
  });

  it("mode 未知 → 原样显示", () => {
    wrap(<ConversationInfoCard conv={{ ...BASE, mode: "weird" }} />);
    expect(screen.getByText("weird")).toBeInTheDocument();
  });

  it("human_pending：显示已等待时长", () => {
    wrap(
      <ConversationInfoCard conv={{ ...BASE, mode: "human_pending", assigned_at: null }} />,
    );
    expect(screen.getByText("已等待")).toBeInTheDocument();
  });

  it("human_takeover：显示接管时长", () => {
    wrap(<ConversationInfoCard conv={BASE} />);
    expect(screen.getByText("接管时长")).toBeInTheDocument();
  });

  it("风险标记：has_failed/downvote 显示对应 Tag", () => {
    wrap(
      <ConversationInfoCard
        conv={{ ...BASE, has_failed: true, has_downvote: 1 }}
      />,
    );
    expect(screen.getByText("失败")).toBeInTheDocument();
    expect(screen.getByText("差评")).toBeInTheDocument();
  });

  it("无任何风险标记：显示 —", () => {
    wrap(<ConversationInfoCard conv={BASE} />);
    // 风险区块下面的 — 与其他 — 一起出现，统计至少一个
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("B 端用户类型显示 BU", () => {
    wrap(<ConversationInfoCard conv={{ ...BASE, user_type: "b" }} />);
    expect(screen.getByText("BU")).toBeInTheDocument();
  });

  it("复制按钮：clipboard 可用时调 writeText", async () => {
    wrap(<ConversationInfoCard conv={BASE} />);
    fireEvent.click(screen.getByRole("button"));
    await waitFor(() =>
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith("u-abc"),
    );
  });

  it("复制按钮：clipboard 不可用时不抛错", async () => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: undefined,
    });
    wrap(<ConversationInfoCard conv={BASE} />);
    expect(() => fireEvent.click(screen.getByRole("button"))).not.toThrow();
  });
});
