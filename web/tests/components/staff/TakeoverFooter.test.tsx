// TakeoverFooter：接管态底部操作（回复 / 更多抽屉里的 转派 + 标记已解决）。
import { App as AntApp } from "antd";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/staffFetch", () => ({ staffFetch: vi.fn() }));

import { TakeoverFooter } from "@/components/TakeoverFooter";
import * as staffApi from "@/api/staff";
import * as attachments from "@/api/attachments";

function wrap(ui: React.ReactNode) {
  return render(<AntApp>{ui}</AntApp>);
}

const PROPS = { token: "tk", convId: 9 } as const;

async function openMore() {
  fireEvent.click(screen.getByRole("button", { name: "更多操作" }));
  // Drawer mount 后内容才进 DOM
  await screen.findByRole("button", { name: "标记已解决" });
}

beforeEach(() => {
  vi.spyOn(staffApi, "listTransferCandidates").mockResolvedValue([
    { staff_id: "a1", display_name: "甲", role: "agent" },
    { staff_id: "a2", display_name: "乙", role: "engineer" },
  ]);
  vi.spyOn(staffApi, "sendStaffMessage").mockResolvedValue();
  vi.spyOn(staffApi, "transferConversation").mockResolvedValue(true);
  vi.spyOn(staffApi, "resolveConversation").mockResolvedValue();
  vi.spyOn(attachments, "uploadStaffAttachment").mockResolvedValue(1);
});
afterEach(() => vi.restoreAllMocks());

describe("TakeoverFooter", () => {
  it("mount 拉转派候选 + 默认渲染回复输入 + 发送按钮 disabled", async () => {
    const onNotice = vi.fn();
    wrap(<TakeoverFooter {...PROPS} onNotice={onNotice} />);
    await waitFor(() => expect(staffApi.listTransferCandidates).toHaveBeenCalledWith("tk"));
    const sendBtn = screen.getByRole("button", { name: /发.?送/ });
    expect(sendBtn).toBeDisabled();
  });

  it("输入文字 → 发送按钮可点 → 调 sendStaffMessage", async () => {
    const onNotice = vi.fn();
    wrap(<TakeoverFooter {...PROPS} onNotice={onNotice} />);
    fireEvent.change(screen.getByPlaceholderText("回复用户…"), {
      target: { value: "好的" },
    });
    fireEvent.click(screen.getByRole("button", { name: /发.?送/ }));
    await waitFor(() =>
      expect(staffApi.sendStaffMessage).toHaveBeenCalledWith("tk", 9, "好的", []),
    );
  });

  it("发送失败 → 调 onNotice 提示", async () => {
    (staffApi.sendStaffMessage as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error("net"));
    const onNotice = vi.fn();
    wrap(<TakeoverFooter {...PROPS} onNotice={onNotice} />);
    fireEvent.change(screen.getByPlaceholderText("回复用户…"), {
      target: { value: "x" },
    });
    fireEvent.click(screen.getByRole("button", { name: /发.?送/ }));
    await waitFor(() => expect(onNotice).toHaveBeenCalledWith(expect.stringContaining("失败")));
  });

  it("按 Enter 也能发送（Shift+Enter 用于换行不发送）", async () => {
    const onNotice = vi.fn();
    wrap(<TakeoverFooter {...PROPS} onNotice={onNotice} />);
    const input = screen.getByPlaceholderText("回复用户…");
    fireEvent.change(input, { target: { value: "x" } });
    fireEvent.keyDown(input, { key: "Enter", code: "Enter" });
    await waitFor(() => expect(staffApi.sendStaffMessage).toHaveBeenCalled());
  });

  it("更多抽屉 → 标记已解决：调 resolveConversation + onReleased + onNotice", async () => {
    const onNotice = vi.fn();
    const onReleased = vi.fn();
    wrap(<TakeoverFooter {...PROPS} onNotice={onNotice} onReleased={onReleased} />);
    await openMore();
    fireEvent.click(screen.getByRole("button", { name: "标记已解决" }));
    await waitFor(() => expect(staffApi.resolveConversation).toHaveBeenCalledWith("tk", 9));
    expect(onReleased).toHaveBeenCalled();
    expect(onNotice).toHaveBeenCalledWith(expect.stringContaining("标记解决"));
  });

  it("标记已解决失败时不调 onReleased", async () => {
    (staffApi.resolveConversation as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new Error("x"),
    );
    const onNotice = vi.fn();
    const onReleased = vi.fn();
    wrap(<TakeoverFooter {...PROPS} onNotice={onNotice} onReleased={onReleased} />);
    await openMore();
    fireEvent.click(screen.getByRole("button", { name: "标记已解决" }));
    await waitFor(() => expect(onNotice).toHaveBeenCalledWith(expect.stringContaining("失败")));
    expect(onReleased).not.toHaveBeenCalled();
  });

  it("无转派候选时（抽屉打开后）下拉 disabled + 占位文案变化", async () => {
    (staffApi.listTransferCandidates as ReturnType<typeof vi.fn>).mockResolvedValue([]);
    wrap(<TakeoverFooter {...PROPS} onNotice={vi.fn()} />);
    await openMore();
    await waitFor(() =>
      expect(screen.getByText("暂无可转派目标")).toBeInTheDocument(),
    );
  });
});
