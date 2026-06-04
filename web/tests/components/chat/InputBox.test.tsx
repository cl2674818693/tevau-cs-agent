// InputBox：Enter 发送 / Shift+Enter 换行 / 粘贴图片上传 / disabled / 发后清空。
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { InputBox } from "@/components/InputBox";
import i18n from "@/i18n";

beforeAll(async () => {
  await i18n.changeLanguage("zh");
});
afterEach(() => vi.restoreAllMocks());

describe("InputBox", () => {
  it("默认渲染：placeholder 默认中文 + 发送按钮 disabled", () => {
    render(<InputBox onSend={vi.fn()} disabled={false} />);
    expect(screen.getByPlaceholderText("描述您的問題…")).toBeInTheDocument();
    expect(screen.getByLabelText("傳送")).toBeDisabled();
  });

  it("自定义 placeholder", () => {
    render(<InputBox onSend={vi.fn()} disabled={false} placeholder="自定义提示" />);
    expect(screen.getByPlaceholderText("自定义提示")).toBeInTheDocument();
  });

  it("输入文字后发送按钮可点", () => {
    render(<InputBox onSend={vi.fn()} disabled={false} />);
    fireEvent.change(screen.getByPlaceholderText("描述您的問題…"), {
      target: { value: "hi" },
    });
    expect(screen.getByLabelText("傳送")).not.toBeDisabled();
  });

  it("点击发送：调 onSend(trim 后的文字)，清空输入", () => {
    const onSend = vi.fn();
    render(<InputBox onSend={onSend} disabled={false} />);
    const ta = screen.getByPlaceholderText("描述您的問題…") as HTMLTextAreaElement;
    fireEvent.change(ta, { target: { value: "  hello  " } });
    fireEvent.click(screen.getByLabelText("傳送"));
    expect(onSend).toHaveBeenCalledWith("hello", []);
    expect(ta.value).toBe("");
  });

  it("Enter 发送", () => {
    const onSend = vi.fn();
    render(<InputBox onSend={onSend} disabled={false} />);
    const ta = screen.getByPlaceholderText("描述您的問題…");
    fireEvent.change(ta, { target: { value: "go" } });
    fireEvent.keyDown(ta, { key: "Enter" });
    expect(onSend).toHaveBeenCalled();
  });

  it("Shift+Enter 不发送（允许换行）", () => {
    const onSend = vi.fn();
    render(<InputBox onSend={onSend} disabled={false} />);
    const ta = screen.getByPlaceholderText("描述您的問題…");
    fireEvent.change(ta, { target: { value: "go" } });
    fireEvent.keyDown(ta, { key: "Enter", shiftKey: true });
    expect(onSend).not.toHaveBeenCalled();
  });

  it("disabled=true：发送按钮 disabled + Enter 不触发", () => {
    const onSend = vi.fn();
    render(<InputBox onSend={onSend} disabled={true} />);
    const ta = screen.getByPlaceholderText("描述您的問題…");
    fireEvent.change(ta, { target: { value: "x" } });
    expect(screen.getByLabelText("傳送")).toBeDisabled();
    fireEvent.keyDown(ta, { key: "Enter" });
    expect(onSend).not.toHaveBeenCalled();
  });

  it("空文本 + 无附件：不发送", () => {
    const onSend = vi.fn();
    render(<InputBox onSend={onSend} disabled={false} />);
    const ta = screen.getByPlaceholderText("描述您的問題…");
    fireEvent.change(ta, { target: { value: "   " } });
    fireEvent.keyDown(ta, { key: "Enter" });
    expect(onSend).not.toHaveBeenCalled();
  });

  it("提供 upload：渲染附件按钮", () => {
    render(<InputBox onSend={vi.fn()} disabled={false} upload={async () => 1} />);
    expect(screen.getByLabelText("attach image")).toBeInTheDocument();
  });

  it("不提供 upload：不渲染附件按钮", () => {
    render(<InputBox onSend={vi.fn()} disabled={false} />);
    expect(screen.queryByLabelText("attach image")).toBeNull();
  });

  it("emoji + 中文长文本可发", () => {
    const onSend = vi.fn();
    render(<InputBox onSend={onSend} disabled={false} />);
    const ta = screen.getByPlaceholderText("描述您的問題…");
    fireEvent.change(ta, { target: { value: "🤖好的".repeat(50) } });
    fireEvent.click(screen.getByLabelText("傳送"));
    expect(onSend.mock.calls[0][0]).toMatch(/🤖好的/);
  });
});
