import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../src/api/staff", () => ({
  sendStaffMessage: vi.fn().mockResolvedValue(undefined),
  resolveConversation: vi.fn().mockResolvedValue(undefined),
  transferConversation: vi.fn().mockResolvedValue(true),
}));
vi.mock("../src/api/attachments", () => ({
  uploadStaffAttachment: vi.fn().mockResolvedValue(7),
  staffAttachmentUrl: (c: number, a: number) => `/staff/api/v1/conversations/${c}/attachments/${a}`,
}));

import { sendStaffMessage } from "../src/api/staff";
import { TakeoverFooter } from "../src/components/TakeoverFooter";

describe("TakeoverFooter image send", () => {
  beforeEach(() => {
    URL.createObjectURL = vi.fn(() => "blob:preview");
    vi.clearAllMocks();
  });

  it("sends with attachment ids", async () => {
    const { container } = render(<TakeoverFooter token="t" convId={3} onNotice={vi.fn()} />);
    const file = new File([new Uint8Array([1])], "a.png", { type: "image/png" });
    fireEvent.change(screen.getByTestId("attach-input"), { target: { files: [file] } });
    await waitFor(() => expect(screen.getByPlaceholderText("回复用户…")).toBeTruthy());
    fireEvent.change(screen.getByPlaceholderText("回复用户…"), { target: { value: "看图" } });
    // antd Button 文本在 jsdom 下不进入 DOM；"发送" = 唯一 .ant-btn-primary
    fireEvent.click(container.querySelector(".ant-btn-primary")!);
    await waitFor(() => expect(sendStaffMessage).toHaveBeenCalledWith("t", 3, "看图", [7]));
  });
});
