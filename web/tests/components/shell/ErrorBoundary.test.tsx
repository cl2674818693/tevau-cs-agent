// ErrorBoundary：子树抛错时兜底；正常渲染时透传；提供 fallback 时优先 fallback。
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { ErrorBoundary } from "@/components/ErrorBoundary";
import i18n from "@/i18n";

beforeAll(async () => {
  await i18n.changeLanguage("zh");
});

function Boom(): JSX.Element {
  throw new Error("boom");
}

let consoleErrorSpy: ReturnType<typeof vi.spyOn>;
beforeEach(() => {
  // React 抛错会 console.error；屏蔽以保持测试 stdout 整洁
  consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
});
afterEach(() => {
  consoleErrorSpy.mockRestore();
});

describe("ErrorBoundary", () => {
  it("正常时透传子树", () => {
    render(
      <ErrorBoundary>
        <div>ok</div>
      </ErrorBoundary>,
    );
    expect(screen.getByText("ok")).toBeInTheDocument();
  });

  it("子树抛错：渲染默认 fallback（标题 + 详情 + 刷新按钮）", () => {
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );
    expect(screen.getByText(/页面出错了/)).toBeInTheDocument();
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /刷新/ })).toBeInTheDocument();
  });

  it("提供自定义 fallback 时优先", () => {
    render(
      <ErrorBoundary fallback={<span>自定义降级</span>}>
        <Boom />
      </ErrorBoundary>,
    );
    expect(screen.getByText("自定义降级")).toBeInTheDocument();
  });

  it("点刷新按钮 → 调 location.reload", () => {
    const reloadSpy = vi.fn();
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { ...window.location, reload: reloadSpy },
      writable: true,
    });
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );
    fireEvent.click(screen.getByRole("button", { name: /刷新/ }));
    expect(reloadSpy).toHaveBeenCalled();
  });
});
