import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ErrorBoundary } from "../src/components/ErrorBoundary";

function Boom(): never {
  throw new Error("boom");
}

describe("ErrorBoundary", () => {
  beforeEach(() => vi.spyOn(console, "error").mockImplementation(() => {}));
  afterEach(() => vi.restoreAllMocks());

  it("子组件抛错时展示兜底 UI 而非白屏", () => {
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );
    expect(screen.getByRole("alert")).toBeTruthy();
    expect(screen.getByText("页面出错了")).toBeTruthy();
  });

  it("正常子组件原样渲染", () => {
    render(
      <ErrorBoundary>
        <div>ok content</div>
      </ErrorBoundary>,
    );
    expect(screen.getByText("ok content")).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
