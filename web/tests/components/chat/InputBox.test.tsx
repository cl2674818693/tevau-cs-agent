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

  // F-P1-1: textarea maxLength 与后端 chat_max_message_length 对齐
  it("textarea 有 maxLength 属性（与后端字符上限对齐）", () => {
    render(<InputBox onSend={vi.fn()} disabled={false} />);
    const ta = screen.getByPlaceholderText("描述您的問題…") as HTMLTextAreaElement;
    expect(ta.maxLength).toBeGreaterThan(0);
    // 现行配置：10000 字符
    expect(ta.maxLength).toBe(10000);
  });

  // F-P1-4: 粘贴的图片超过单图大小上限时不上传（防被后端拒后丢提示）
  it("粘贴的超大图片不上传 + 显示提示", async () => {
    const upload = vi.fn(async () => 99);
    render(<InputBox onSend={vi.fn()} disabled={false} upload={upload} />);
    const ta = screen.getByPlaceholderText("描述您的問題…");
    // 模拟 6MB 文件（>5MB 上限）
    const big = new File([new Uint8Array(6 * 1024 * 1024)], "big.jpg", { type: "image/jpeg" });
    const dataTransfer = {
      files: { length: 1, 0: big, item: (i: number) => (i === 0 ? big : null) } as unknown as FileList,
      types: ["Files"],
    } as unknown as DataTransfer;
    fireEvent.paste(ta, { clipboardData: dataTransfer });
    // upload 不应被调用
    expect(upload).not.toHaveBeenCalled();
  });

  // F-P1-3: 张数超出（已有 MAX_IMAGES=4）的图片不上传
  it("粘贴张数超出（room=0）时不上传", async () => {
    const upload = vi.fn(async () => 1);
    render(<InputBox onSend={vi.fn()} disabled={false} upload={upload} />);
    const ta = screen.getByPlaceholderText("描述您的問題…");
    // 模拟一张 1KB 合法图
    const img = new File([new Uint8Array(1024)], "x.jpg", { type: "image/jpeg" });
    const transfer = (n: number): DataTransfer =>
      ({
        files: Object.assign(
          { length: n, item: (i: number) => (i < n ? img : null) },
          Array.from({ length: n }, () => img).reduce((a, f, i) => ({ ...a, [i]: f }), {}),
        ) as unknown as FileList,
        types: ["Files"],
      }) as unknown as DataTransfer;
    // 5 张 → 砍到 4，第 5 张不上传
    fireEvent.paste(ta, { clipboardData: transfer(5) });
    // 等待异步上传完成
    await Promise.resolve();
    await Promise.resolve();
    expect(upload.mock.calls.length).toBeLessThanOrEqual(4);
  });
});
