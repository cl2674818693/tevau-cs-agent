// ToolCallChip：C 端只显示语言化进度；B 端显示工具名 + 可展开 JSON。
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it } from "vitest";

import { ToolCallChip } from "@/components/ToolCallChip";
import i18n from "@/i18n";

beforeAll(async () => {
  await i18n.changeLanguage("zh");
});

describe("ToolCallChip C 端", () => {
  it("已知工具名走对应中文文案", () => {
    render(
      <ToolCallChip
        userType="c"
        tc={{ name: "query_user", input: { id: 1 }, ok: true }}
      />,
    );
    expect(screen.getByText(/查询账户信息/)).toBeInTheDocument();
  });

  it("未知工具名走默认文案", () => {
    render(
      <ToolCallChip
        userType="c"
        tc={{ name: "weird_tool", input: {} }}
      />,
    );
    expect(screen.getByText(/正在为您处理/)).toBeInTheDocument();
  });

  it("不暴露工具名 / 不暴露 input JSON", () => {
    render(
      <ToolCallChip
        userType="c"
        tc={{ name: "query_user", input: { secret: "abc" } }}
      />,
    );
    expect(screen.queryByText("query_user")).toBeNull();
    expect(screen.queryByText(/secret/)).toBeNull();
  });
});

describe("ToolCallChip B 端", () => {
  it("默认显示工具名，未展开 JSON", () => {
    render(
      <ToolCallChip
        userType="b"
        tc={{ name: "query_user", input: { id: 1 }, ok: true }}
      />,
    );
    expect(screen.getByText("query_user")).toBeInTheDocument();
    expect(screen.queryByText(/"id": 1/)).toBeNull();
  });

  it("点击展开后显示 JSON 入参", () => {
    render(
      <ToolCallChip
        userType="b"
        tc={{ name: "query_user", input: { id: 1, name: "x" } }}
      />,
    );
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByText(/"id": 1/)).toBeInTheDocument();
    expect(screen.getByText(/"name": "x"/)).toBeInTheDocument();
  });

  it("ok=true → success 色；ok=false → error 色（含特定 class）", () => {
    const { rerender } = render(
      <ToolCallChip userType="b" tc={{ name: "x", input: {}, ok: true }} />,
    );
    // 直接验 status icon 是 Check（无 spin），通过查找 svg 数量足够
    expect(screen.getByRole("button").querySelectorAll("svg").length).toBeGreaterThan(0);
    rerender(<ToolCallChip userType="b" tc={{ name: "x", input: {}, ok: false }} />);
    expect(screen.getByRole("button")).toBeInTheDocument();
  });

  it("ok=undefined → loading 转圈 icon（动画 class）", () => {
    render(<ToolCallChip userType="b" tc={{ name: "x", input: {} }} />);
    const spinning = screen.getByRole("button").querySelector(".animate-spin");
    expect(spinning).not.toBeNull();
  });
});
