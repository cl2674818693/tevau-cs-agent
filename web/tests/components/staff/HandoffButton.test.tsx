// HandoffPrompt：内联转人工按钮。
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";

import { HandoffPrompt } from "@/components/HandoffButton";
import i18n from "@/i18n";

beforeAll(async () => {
  await i18n.changeLanguage("zh");
});

describe("HandoffPrompt", () => {
  it("默认渲染中文按钮", () => {
    render(<HandoffPrompt onClick={() => {}} disabled={false} />);
    expect(screen.getByRole("button", { name: /没解决/ })).toBeInTheDocument();
  });

  it("点击触发 onClick", () => {
    const onClick = vi.fn();
    render(<HandoffPrompt onClick={onClick} disabled={false} />);
    fireEvent.click(screen.getByRole("button"));
    expect(onClick).toHaveBeenCalled();
  });

  it("disabled=true：按钮 disabled + 点击不触发", () => {
    const onClick = vi.fn();
    render(<HandoffPrompt onClick={onClick} disabled={true} />);
    const btn = screen.getByRole("button");
    expect(btn).toBeDisabled();
    fireEvent.click(btn);
    expect(onClick).not.toHaveBeenCalled();
  });
});
