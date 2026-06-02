// AiDraftPanel：渲染草稿 + 直接发出 / 改写后发 + 提交中 disabled + draft=null 隐藏
import { App as AntApp } from "antd";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AiDraftPanel } from "@/components/AiDraftPanel";

function wrap(ui: React.ReactNode) {
  return render(<AntApp>{ui}</AntApp>);
}

afterEach(() => vi.restoreAllMocks());

describe("AiDraftPanel", () => {
  it("draft=null：什么都不渲染", () => {
    const { container } = wrap(
      <AiDraftPanel draft={null} onApprove={vi.fn()} onReject={vi.fn()} />,
    );
    expect(container.textContent).toBe("");
  });

  it("draft 非空：默认非编辑态，显示原文 + 直接发出/改写按钮", () => {
    wrap(<AiDraftPanel draft="您好" onApprove={vi.fn()} onReject={vi.fn()} />);
    expect(screen.getByText("您好")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "直接发出" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "改写" })).toBeInTheDocument();
  });

  it("点直接发出 → 调 onApprove", async () => {
    const onApprove = vi.fn().mockResolvedValue(undefined);
    wrap(<AiDraftPanel draft="x" onApprove={onApprove} onReject={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "直接发出" }));
    await waitFor(() => expect(onApprove).toHaveBeenCalled());
  });

  it("提交中（onApprove pending）→ 按钮 disabled，避免重复提交", async () => {
    let resolve!: () => void;
    const onApprove = vi.fn(
      () => new Promise<void>((r) => { resolve = r; }),
    );
    wrap(<AiDraftPanel draft="x" onApprove={onApprove} onReject={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "直接发出" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /直接发出/ })).toBeDisabled(),
    );
    resolve();
    await waitFor(() => expect(onApprove).toHaveBeenCalled());
  });

  it("点改写 → 切到编辑态显示 TextArea + 改写后发送按钮", () => {
    wrap(<AiDraftPanel draft="hello" onApprove={vi.fn()} onReject={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "改写" }));
    expect(screen.getByRole("textbox")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /改写后发.?送/ })).toBeInTheDocument();
  });

  it("改写后清空 trim 为空 → 按钮 disabled", () => {
    wrap(<AiDraftPanel draft="hi" onApprove={vi.fn()} onReject={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "改写" }));
    const ta = screen.getByRole("textbox") as HTMLTextAreaElement;
    fireEvent.change(ta, { target: { value: "  " } });
    expect(screen.getByRole("button", { name: /改写后发.?送/ })).toBeDisabled();
  });

  it("改写后发送 → 调 onReject(trim后内容)", async () => {
    const onReject = vi.fn().mockResolvedValue(undefined);
    wrap(<AiDraftPanel draft="原" onApprove={vi.fn()} onReject={onReject} />);
    fireEvent.click(screen.getByRole("button", { name: "改写" }));
    const ta = screen.getByRole("textbox");
    fireEvent.change(ta, { target: { value: "  新内容  " } });
    fireEvent.click(screen.getByRole("button", { name: /改写后发.?送/ }));
    await waitFor(() => expect(onReject).toHaveBeenCalledWith("新内容"));
  });

  it("draft 更新时：清空 rewrite + 复位 editing/submitting", () => {
    const { rerender } = wrap(
      <AiDraftPanel draft="一稿" onApprove={vi.fn()} onReject={vi.fn()} />,
    );
    fireEvent.click(screen.getByRole("button", { name: "改写" }));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "改完" } });
    rerender(
      <AntApp>
        <AiDraftPanel draft="二稿" onApprove={vi.fn()} onReject={vi.fn()} />
      </AntApp>,
    );
    // 应复位回非编辑态
    expect(screen.queryByRole("textbox")).toBeNull();
    expect(screen.getByText("二稿")).toBeInTheDocument();
  });
});
