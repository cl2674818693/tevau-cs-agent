// AiToolsPanel：客服代查工具，参数 JSON 校验，结果展示。
import { App as AntApp } from "antd";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/staffFetch", () => ({ staffFetch: vi.fn() }));

import { AiToolsPanel } from "@/components/AiToolsPanel";
import * as staffApi from "@/api/staff";

function wrap(ui: React.ReactNode) {
  return render(<AntApp>{ui}</AntApp>);
}

beforeEach(() => vi.restoreAllMocks());
afterEach(() => vi.restoreAllMocks());

describe("AiToolsPanel", () => {
  it("默认渲染：工具下拉 + 参数 JSON 区 + 运行按钮", () => {
    wrap(<AiToolsPanel token="tk" convId={1} />);
    expect(screen.getByLabelText("工具参数 JSON")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /运.?行/ })).toBeInTheDocument();
  });

  it("参数 JSON 非法时不调后端，显示错误", () => {
    const spy = vi.spyOn(staffApi, "runAiTool");
    wrap(<AiToolsPanel token="tk" convId={1} />);
    fireEvent.change(screen.getByLabelText("工具参数 JSON"), {
      target: { value: "{ not json" },
    });
    fireEvent.click(screen.getByRole("button", { name: /运.?行/ }));
    expect(spy).not.toHaveBeenCalled();
    expect(screen.getByText("参数不是合法 JSON")).toBeInTheDocument();
  });

  it("运行成功：展示 result.data JSON", async () => {
    vi.spyOn(staffApi, "runAiTool").mockResolvedValue({
      ok: true,
      data: { id: 7, name: "foo" },
    });
    wrap(<AiToolsPanel token="tk" convId={1} />);
    fireEvent.click(screen.getByRole("button", { name: /运.?行/ }));
    await waitFor(() => expect(screen.getByText(/"id": 7/)).toBeInTheDocument());
    expect(screen.getByText(/"name": "foo"/)).toBeInTheDocument();
  });

  it("运行失败：展示 error 字符串", async () => {
    vi.spyOn(staffApi, "runAiTool").mockResolvedValue({
      ok: false,
      error: "no permission",
    });
    wrap(<AiToolsPanel token="tk" convId={1} />);
    fireEvent.click(screen.getByRole("button", { name: /运.?行/ }));
    await waitFor(() =>
      expect(screen.getByText(/错误：no permission/)).toBeInTheDocument(),
    );
  });

  it("运行中按钮 loading 状态", async () => {
    let resolve!: (v: unknown) => void;
    vi.spyOn(staffApi, "runAiTool").mockReturnValue(
      new Promise((r) => {
        resolve = r;
      }) as Promise<staffApi.AiToolResult>,
    );
    wrap(<AiToolsPanel token="tk" convId={1} />);
    fireEvent.click(screen.getByRole("button", { name: /运.?行/ }));
    // antd Button loading 状态下可读到 .ant-btn-loading class
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /运.?行/ }).className).toMatch(/loading/),
    );
    resolve({ ok: true, data: null });
  });
});
