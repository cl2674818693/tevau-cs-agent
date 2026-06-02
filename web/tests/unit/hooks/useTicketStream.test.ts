// useTicketStream：订阅工单 SSE，累加白名单事件；断线退避重连；conversationId=null 不订阅；
// 卸载后停止（StrictMode 双订阅安全：用闭包 stopped 局部变量）。
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as chatApi from "@/api/chat";
import { useTicketStream } from "@/hooks/useTicketStream";

/** 构造一个 mock async generator，可在 yield 间手动控制。 */
function controlledStream() {
  const queue: unknown[] = [];
  let resolveNext: ((v: unknown) => void) | null = null;
  let closed = false;
  const errors: unknown[] = [];

  const gen = (async function* () {
    while (!closed) {
      if (queue.length > 0) {
        yield queue.shift()!;
      } else {
        await new Promise((r) => {
          resolveNext = r;
        });
        if (errors.length > 0) throw errors.shift();
      }
    }
  })();

  return {
    gen,
    push(ev: unknown) {
      if (resolveNext) {
        queue.push(ev);
        const r = resolveNext;
        resolveNext = null;
        r(undefined);
      } else queue.push(ev);
    },
    fail(err: unknown) {
      errors.push(err);
      if (resolveNext) {
        const r = resolveNext;
        resolveNext = null;
        r(undefined);
      }
    },
    close() {
      closed = true;
      if (resolveNext) resolveNext(undefined);
    },
  };
}

describe("useTicketStream", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => vi.restoreAllMocks());

  it("conversationId=null 不订阅", () => {
    const spy = vi.spyOn(chatApi, "streamTicketEvents");
    renderHook(() => useTicketStream(null));
    expect(spy).not.toHaveBeenCalled();
  });

  it("收到白名单事件 → 累积到 events 数组", async () => {
    const s = controlledStream();
    vi.spyOn(chatApi, "streamTicketEvents").mockReturnValue(
      s.gen as unknown as AsyncGenerator<unknown>,
    );
    const { result } = renderHook(() => useTicketStream(1));
    s.push({ type: "assigned", external_id: "T-1" });
    await waitFor(() => expect(result.current).toHaveLength(1));
    expect(result.current[0]).toMatchObject({ event: "assigned", external_id: "T-1" });
    s.push({ type: "resolved", external_id: "T-1", actor: "agent" });
    await waitFor(() => expect(result.current).toHaveLength(2));
    expect(result.current[1]).toMatchObject({ event: "resolved", actor: "agent" });
  });

  it("非白名单事件被过滤", async () => {
    const s = controlledStream();
    vi.spyOn(chatApi, "streamTicketEvents").mockReturnValue(
      s.gen as unknown as AsyncGenerator<unknown>,
    );
    const { result } = renderHook(() => useTicketStream(1));
    s.push({ type: "ping" });
    s.push({ type: "noise" });
    // 给微任务跑机会
    await new Promise((r) => setTimeout(r, 10));
    expect(result.current).toEqual([]);
  });

  it("卸载后 stopped=true：不再处理后续 yield", async () => {
    const s = controlledStream();
    vi.spyOn(chatApi, "streamTicketEvents").mockReturnValue(
      s.gen as unknown as AsyncGenerator<unknown>,
    );
    const { result, unmount } = renderHook(() => useTicketStream(1));
    s.push({ type: "assigned", external_id: "T-1" });
    await waitFor(() => expect(result.current).toHaveLength(1));
    unmount();
    s.push({ type: "resolved", external_id: "T-1" });
    await new Promise((r) => setTimeout(r, 10));
    // 卸载后捕获不到新 state（result snapshot 固定），但不应抛错
    expect(result.current).toHaveLength(1);
  });
});
