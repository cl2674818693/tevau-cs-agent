import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AttachButton } from "../src/components/AttachButton";

describe("AttachButton", () => {
  beforeEach(() => {
    // jsdom 无 URL.createObjectURL，缩略图预览用
    URL.createObjectURL = vi.fn(() => "blob:preview");
  });

  it("uploads picked file and reports id", async () => {
    const upload = vi.fn().mockResolvedValue(42);
    const onChange = vi.fn();
    render(<AttachButton upload={upload} ids={[]} onChange={onChange} max={4} />);
    const file = new File([new Uint8Array([1])], "a.png", { type: "image/png" });
    const input = screen.getByTestId("attach-input") as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });
    await waitFor(() => expect(upload).toHaveBeenCalledWith(file));
    await waitFor(() => expect(onChange).toHaveBeenCalledWith([42]));
  });

  it("disables the button at max", () => {
    render(<AttachButton upload={vi.fn()} ids={[1, 2, 3, 4]} onChange={vi.fn()} max={4} />);
    expect((screen.getByLabelText("attach image") as HTMLButtonElement).disabled).toBe(true);
  });
});
