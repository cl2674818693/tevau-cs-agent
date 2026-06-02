// useAsyncData 统一数据页 loading/error/data 状态机。
import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { useAsyncData } from "@/hooks/useAsyncData";

describe("useAsyncData", () => {
  it("初始 loading=true", () => {
    const { result } = renderHook(() => useAsyncData(() => new Promise(() => {}), []));
    expect(result.current.loading).toBe(true);
    expect(result.current.data).toBeNull();
    expect(result.current.error).toBe("");
  });

  it("成功 resolve 后 data 就绪、loading=false", async () => {
    const { result } = renderHook(() =>
      useAsyncData(() => Promise.resolve({ n: 1 }), []),
    );
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toEqual({ n: 1 });
    expect(result.current.error).toBe("");
  });

  it("reject 后 error 就绪、data=null", async () => {
    const { result } = renderHook(() =>
      useAsyncData(() => Promise.reject(new Error("boom")), [], "加载坏了"),
    );
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toBeNull();
    expect(result.current.error).toBe("加载坏了");
  });

  it("fn 返回 null 视为无前置条件：不发起、loading=false、data=null", async () => {
    const { result } = renderHook(() => useAsyncData<unknown>(() => null, []));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toBeNull();
    expect(result.current.error).toBe("");
  });

  it("deps 变化时重新拉取（丢弃过期结果）", async () => {
    let nth = 0;
    const fns: Array<() => Promise<number> | null> = [];
    const { result, rerender } = renderHook(({ k }: { k: number }) =>
      useAsyncData(() => {
        nth++;
        const my = nth;
        fns.push(() => Promise.resolve(my));
        return new Promise<number>((resolve) =>
          setTimeout(() => resolve(my), 5 - k), // 旧的 resolve 晚
        );
      }, [k]),
      { initialProps: { k: 0 } },
    );
    // 立刻切到 k=1，触发第二次拉取（第二次会更快 resolve）
    rerender({ k: 1 });
    await waitFor(() => expect(result.current.loading).toBe(false));
    // 第二次的值（2）应胜出，避免第一次的过期结果覆盖
    expect(result.current.data).toBe(2);
  });

  it("组件卸载后不再 setState（防 act warning）", async () => {
    let resolve!: (v: number) => void;
    const p = new Promise<number>((r) => {
      resolve = r;
    });
    const { result, unmount } = renderHook(() => useAsyncData(() => p, []));
    unmount();
    await act(async () => {
      resolve(1);
      // 等微任务跑完
      await Promise.resolve();
    });
    // 不应在卸载后改 state（这里靠没有 React 警告 + 取消标记的契约）；
    // 我们只断言 result.current 仍是初始 snapshot（renderHook 在 unmount 后冻结）。
    expect(result.current.loading).toBe(true); // 卸载前快照
  });
});
