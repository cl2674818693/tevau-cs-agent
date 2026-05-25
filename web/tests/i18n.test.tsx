import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ChatHeader } from "../src/components/ChatExtras";
import i18n from "../src/i18n";

afterEach(() => i18n.changeLanguage("zh"));

describe("i18n", () => {
  it("默认中文渲染客户面文案", () => {
    render(<ChatHeader mode="ai" sending={false} onStop={() => {}} />);
    expect(screen.getByText("Tevau AI 客服")).toBeTruthy();
    expect(screen.getByText("由 AI 驱动 · 复杂问题转人工")).toBeTruthy();
  });

  it("切到英文后渲染英文文案", async () => {
    await i18n.changeLanguage("en");
    render(<ChatHeader mode="ai" sending={false} onStop={() => {}} />);
    expect(screen.getByText("Tevau AI Support")).toBeTruthy();
    expect(screen.getByText(/AI-powered/)).toBeTruthy();
  });
});
