// StaffImageThumb：客服侧 Bearer 取图；失败/加载/成功三态。
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { StaffImageThumb } from "@/components/StaffImageThumb";

beforeEach(() => {
  if (typeof URL.createObjectURL !== "function") {
    Object.defineProperty(URL, "createObjectURL", { value: () => "blob:x", writable: true });
  }
});
afterEach(() => vi.restoreAllMocks());

describe("StaffImageThumb", () => {
  it("加载中：显示 Skeleton 占位", () => {
    vi.spyOn(globalThis, "fetch").mockReturnValue(new Promise(() => {}) as Promise<Response>);
    const { container } = render(<StaffImageThumb src="/staff/img/1" token="tk" />);
    // antd Skeleton 渲染出特定 class
    expect(container.querySelector(".ant-skeleton-image")).toBeTruthy();
  });

  it("成功后显示 antd Image", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(new Blob(["x"]), { status: 200 }),
    );
    render(<StaffImageThumb src="/staff/img/1" token="tk" />);
    await waitFor(() => expect(screen.getAllByRole("img").length).toBeGreaterThan(0));
  });

  it("失败显示文案", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("", { status: 403 }));
    render(<StaffImageThumb src="/staff/img/1" token="tk" />);
    await waitFor(() => expect(screen.getByText(/加载失败/)).toBeInTheDocument());
  });

  it("src/token 改变重新拉取", async () => {
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(new Blob(["x"]), { status: 200 }));
    const { rerender } = render(<StaffImageThumb src="/x" token="t1" />);
    await waitFor(() => expect(spy).toHaveBeenCalled());
    spy.mockClear();
    rerender(<StaffImageThumb src="/y" token="t1" />);
    await waitFor(() => expect(spy).toHaveBeenCalled());
  });
});
