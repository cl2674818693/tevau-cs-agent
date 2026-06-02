// AttachButton：受控选图、上传中 disable、删除、父清空时本地预览也清掉。
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { AttachButton } from "@/components/AttachButton";

beforeAll(() => {
  // jsdom 没有 URL.createObjectURL / revokeObjectURL
  if (typeof URL.createObjectURL !== "function") {
    Object.defineProperty(URL, "createObjectURL", { value: () => "blob:fake", writable: true });
  }
  if (typeof URL.revokeObjectURL !== "function") {
    Object.defineProperty(URL, "revokeObjectURL", { value: () => {}, writable: true });
  }
});
afterEach(() => vi.restoreAllMocks());

function pngFile(name = "a.png") {
  return new File([new Uint8Array([0x89, 0x50, 0x4e, 0x47])], name, { type: "image/png" });
}

describe("AttachButton", () => {
  it("默认渲染附件按钮 + 隐藏的 input", () => {
    render(
      <AttachButton upload={async () => 1} ids={[]} onChange={vi.fn()} max={4} />,
    );
    expect(screen.getByLabelText("attach image")).toBeInTheDocument();
  });

  it("disabled=true：按钮 disabled", () => {
    render(
      <AttachButton upload={async () => 1} ids={[]} onChange={vi.fn()} max={4} disabled />,
    );
    expect(screen.getByLabelText("attach image")).toBeDisabled();
  });

  it("选图后调 upload，并把 id 加入 onChange", async () => {
    const upload = vi.fn(async () => 7);
    const onChange = vi.fn();
    render(<AttachButton upload={upload} ids={[]} onChange={onChange} max={4} />);
    const input = screen.getByTestId("attach-input") as HTMLInputElement;
    Object.defineProperty(input, "files", { value: [pngFile()] });
    fireEvent.change(input);
    await waitFor(() => expect(upload).toHaveBeenCalled());
    expect(onChange).toHaveBeenCalledWith([7]);
  });

  it("超过 max 时只上传 room 数量", async () => {
    const upload = vi.fn(async () => 1);
    const onChange = vi.fn();
    render(<AttachButton upload={upload} ids={[1, 2, 3]} onChange={onChange} max={4} />);
    const input = screen.getByTestId("attach-input") as HTMLInputElement;
    Object.defineProperty(input, "files", { value: [pngFile("a"), pngFile("b"), pngFile("c")] });
    fireEvent.change(input);
    await waitFor(() => expect(upload).toHaveBeenCalledTimes(1));
  });

  it("ids 长度 = max 时按钮 disabled", () => {
    render(
      <AttachButton upload={async () => 1} ids={[1, 2, 3, 4]} onChange={vi.fn()} max={4} />,
    );
    expect(screen.getByLabelText("attach image")).toBeDisabled();
  });

  it("点 X 删除附件 → onChange 排除该 id", async () => {
    const upload = vi.fn(async () => 9);
    const onChange = vi.fn();
    const { container } = render(
      <AttachButton upload={upload} ids={[]} onChange={onChange} max={4} />,
    );
    const input = screen.getByTestId("attach-input") as HTMLInputElement;
    Object.defineProperty(input, "files", { value: [pngFile()] });
    fireEvent.change(input);
    await waitFor(() => expect(onChange).toHaveBeenCalled());
    await waitFor(() => expect(container.querySelector("img")).toBeTruthy());
    onChange.mockClear();
    fireEvent.click(screen.getByLabelText("remove"));
    expect(onChange).toHaveBeenCalledWith([]);
  });

  it("父清空 ids 后本地 pending 预览同步清空（防残留）", async () => {
    const upload = vi.fn(async () => 99);
    const onChange = vi.fn();
    // 真实场景：父持有 ids 受控；上传后 ids=[99]，发送成功后父复位为 []。
    const { container, rerender } = render(
      <AttachButton upload={upload} ids={[]} onChange={onChange} max={4} />,
    );
    const input = screen.getByTestId("attach-input") as HTMLInputElement;
    Object.defineProperty(input, "files", { value: [pngFile()] });
    fireEvent.change(input);
    await waitFor(() => expect(container.querySelector("img")).toBeTruthy());
    // 模拟父：上传完 ids 变为 [99]
    rerender(<AttachButton upload={upload} ids={[99]} onChange={onChange} max={4} />);
    // 发送成功，父复位 ids=[] —— 触发 effect 清空 pending
    rerender(<AttachButton upload={upload} ids={[]} onChange={onChange} max={4} />);
    await waitFor(() => expect(container.querySelector("img")).toBeNull());
  });
});
