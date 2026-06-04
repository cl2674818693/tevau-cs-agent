// ToolCallChip：C/B 聊天面（APP + BU 自助页）一律语言化进度，不暴露工具名 / JSON。
// staff 后台用 EventBubble 不走此组件。
import { render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it } from "vitest";

import { ToolCallChip } from "@/components/ToolCallChip";
import i18n from "@/i18n";

beforeAll(async () => {
  await i18n.changeLanguage("zh");
});

describe("ToolCallChip", () => {
  it("已知工具名走对应中文文案", () => {
    render(<ToolCallChip tc={{ name: "query_user", input: { id: 1 }, ok: true }} />);
    expect(screen.getByText(/查詢帳戶資訊/)).toBeInTheDocument();
  });

  it("未知工具名走默认文案", () => {
    render(<ToolCallChip tc={{ name: "weird_tool", input: {} }} />);
    expect(screen.getByText(/正在為您處理/)).toBeInTheDocument();
  });

  it("不暴露工具名 / 不暴露 input JSON", () => {
    render(<ToolCallChip tc={{ name: "query_user", input: { secret: "abc" } }} />);
    expect(screen.queryByText("query_user")).toBeNull();
    expect(screen.queryByText(/secret/)).toBeNull();
  });

  it("B 端身份同样走语言化进度（不再有工具名按钮）", () => {
    render(
      <ToolCallChip
        userType="b"
        tc={{ name: "query_bu_card", input: { card_id: "x" }, ok: true }}
      />,
    );
    expect(screen.queryByText("query_bu_card")).toBeNull();
    expect(screen.getByText(/查詢卡片資訊/)).toBeInTheDocument();
  });

  it("ok=undefined 时显示 loading 动画 icon", () => {
    const { container } = render(<ToolCallChip tc={{ name: "x", input: {} }} />);
    expect(container.querySelector(".animate-spin")).not.toBeNull();
  });
});
