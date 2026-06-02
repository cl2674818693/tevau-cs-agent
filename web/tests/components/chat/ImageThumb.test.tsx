// ImageThumb：带鉴权取图片字节 + 点击放大 + 失败显示提示。
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ImageThumb } from "@/components/ImageThumb";

afterEach(() => vi.restoreAllMocks());

describe("ImageThumb", () => {
  it("初始渲染加载占位（无 img）", () => {
    render(<ImageThumb src="/img/1" resolve={() => new Promise(() => "blob:x")} />);
    expect(screen.queryByRole("img")).toBeNull();
  });

  it("resolve 成功 → 显示 img", async () => {
    render(<ImageThumb src="/img/1" resolve={async () => "blob:x"} />);
    await waitFor(() => expect(screen.getByRole("img")).toBeInTheDocument());
  });

  it("resolve 失败 → 显示失败文案", async () => {
    render(<ImageThumb src="/img/1" resolve={async () => { throw new Error("net"); }} />);
    await waitFor(() => expect(screen.getByText(/加载失败/)).toBeInTheDocument());
  });

  it("点击 img → 打开全屏遮罩；点遮罩 → 关闭", async () => {
    const { container } = render(
      <ImageThumb src="/img/1" resolve={async () => "blob:x"} />,
    );
    const img = await screen.findByRole("img");
    fireEvent.click(img);
    // 全屏放大版 alt='' 不算 role=img，转用 DOM 检索覆盖层
    const overlay = await waitFor(() => {
      const o = container.ownerDocument.querySelector(".fixed.inset-0");
      if (!o) throw new Error("overlay not found");
      return o as HTMLElement;
    });
    fireEvent.click(overlay);
    await waitFor(() =>
      expect(container.ownerDocument.querySelector(".fixed.inset-0")).toBeNull(),
    );
  });

  it("src 变更触发重新拉取", async () => {
    const resolve = vi.fn(async (s: string) => `blob:${s}`);
    const { rerender } = render(<ImageThumb src="/img/1" resolve={resolve} />);
    await waitFor(() => expect(resolve).toHaveBeenCalledWith("/img/1"));
    rerender(<ImageThumb src="/img/2" resolve={resolve} />);
    await waitFor(() => expect(resolve).toHaveBeenCalledWith("/img/2"));
  });
});
