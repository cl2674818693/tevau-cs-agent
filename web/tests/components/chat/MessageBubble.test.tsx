// MessageBubble：根据 role 渲染不同气泡 + 反馈条 + 附件 + 工具调用。
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { MessageBubble } from "@/components/MessageBubble";
import i18n from "@/i18n";

beforeAll(async () => {
  await i18n.changeLanguage("zh");
});

afterEach(() => vi.restoreAllMocks());

describe("MessageBubble", () => {
  it("system 角色：居中胶囊文本", () => {
    render(<MessageBubble m={{ role: "system", content: "已连接" }} />);
    expect(screen.getByText("已连接")).toBeInTheDocument();
  });

  it("user 角色：渲染文字内容（无附件时不出图片）", () => {
    render(<MessageBubble m={{ role: "user", content: "你好" }} />);
    expect(screen.getByText("你好")).toBeInTheDocument();
    expect(screen.queryByRole("img")).toBeNull();
  });

  it("user 角色 + 附件：urlFor 提供时渲染缩略图占位", () => {
    render(
      <MessageBubble
        m={{
          role: "user",
          content: "看图",
          attachments: [{ id: 1, mime: "image/jpeg" }],
        }}
        urlFor={(id) => `/img/${id}`}
      />,
    );
    expect(screen.getByText("看图")).toBeInTheDocument();
    // ImageThumb 内部用 resolve→objectURL，初始态渲染骨架（无 img）；这里只验文字落地
  });

  it("user 角色 + 附件 + urlFor 缺省：附件块不渲染", () => {
    const { container } = render(
      <MessageBubble
        m={{ role: "user", content: "", attachments: [{ id: 1, mime: "image/jpeg" }] }}
      />,
    );
    // 没有任何 ImageThumb / pre/cn 区域；user 行存在但内容/附件均空
    expect(container.textContent ?? "").toBe("");
  });

  it("human_agent 角色：显示 ✓ 已认证 + 文字（不暴露 display_name）", () => {
    render(
      <MessageBubble
        m={{ role: "human_agent", content: "您好", display_name: "小王" }}
      />,
    );
    expect(screen.getByText("您好")).toBeInTheDocument();
    expect(screen.getByText("已认证")).toBeInTheDocument();
    // 客服花名/真名不应出现在 UI
    expect(screen.queryByText("小王")).toBeNull();
  });

  it("assistant 内容为空时显示思考中...占位", () => {
    render(<MessageBubble m={{ role: "assistant", content: "" }} />);
    expect(screen.getByText("思考中…")).toBeInTheDocument();
  });

  it("assistant 内容非空 + 反馈回调：渲染 👍/👎 反馈条", () => {
    const onFb = vi.fn();
    render(
      <MessageBubble
        m={{ role: "assistant", content: "答案是 42" }}
        onFeedback={onFb}
      />,
    );
    expect(screen.getByText("答案是 42")).toBeInTheDocument();
    const up = screen.getByLabelText("有帮助");
    const down = screen.getByLabelText("没帮助");
    fireEvent.click(up);
    expect(onFb).toHaveBeenCalledWith("up");
    // 点过即锁定 → 显示致谢
    expect(screen.getByText(/感谢反馈/)).toBeInTheDocument();
    // 锁定后不能再点
    expect(screen.queryByLabelText("没帮助")).toBeNull();
    void down; // 防 lint 未用
  });

  it("反馈：英文内容 → 英文反馈文案（langOf 走 en）", () => {
    render(
      <MessageBubble m={{ role: "assistant", content: "Hello there" }} onFeedback={() => {}} />,
    );
    expect(screen.getByLabelText("Helpful")).toBeInTheDocument();
    expect(screen.getByLabelText("Not helpful")).toBeInTheDocument();
  });

  it("assistant 含 tool_calls：c 端展示语言化进度", () => {
    render(
      <MessageBubble
        m={{
          role: "assistant",
          content: "查到了",
          tool_calls: [{ name: "query_user", input: { id: 1 }, ok: true }],
        }}
        userType="c"
      />,
    );
    // 工具进度文案：toolChip.query_user
    expect(screen.getByText(/查询账户信息/)).toBeInTheDocument();
  });

  it("assistant 含 tool_calls：b 端展示工具名 + 可展开 JSON", () => {
    render(
      <MessageBubble
        m={{
          role: "assistant",
          content: "ok",
          tool_calls: [{ name: "query_user", input: { id: 1 }, ok: true }],
        }}
        userType="b"
      />,
    );
    // 工具名 query_user 直接显示
    expect(screen.getByText("query_user")).toBeInTheDocument();
  });

  it("中文 emoji + 极长文本不抛错", () => {
    const long = "🤖你好" + "的".repeat(2000);
    render(<MessageBubble m={{ role: "user", content: long }} />);
    expect(screen.getByText(long)).toBeInTheDocument();
  });

  it("无 onFeedback 时不渲染反馈条", () => {
    render(<MessageBubble m={{ role: "assistant", content: "ok" }} />);
    expect(screen.queryByLabelText("有帮助")).toBeNull();
  });
});
