// backoff 指数退避算法的边界与确定性测试。
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { backoffDelay } from "@/lib/backoff";

describe("backoffDelay 指数退避", () => {
  beforeEach(() => {
    // 固定随机：让 [half, half+half*rand] 落到确定值，便于断言公式。
    vi.spyOn(Math, "random").mockReturnValue(0);
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("attempt=0 时延迟 = base/2（jitter=0）", () => {
    expect(backoffDelay(0, { base: 1000, max: 30000 })).toBe(500);
  });

  it("attempt 增长时指数翻倍上界", () => {
    expect(backoffDelay(1, { base: 1000, max: 30000 })).toBe(1000);
    expect(backoffDelay(2, { base: 1000, max: 30000 })).toBe(2000);
    expect(backoffDelay(3, { base: 1000, max: 30000 })).toBe(4000);
  });

  it("attempt 极大时不超过 max", () => {
    expect(backoffDelay(20, { base: 1000, max: 30000 })).toBe(15000); // max/2，因 random=0
  });

  it("负 attempt 视为 0", () => {
    expect(backoffDelay(-5, { base: 1000, max: 30000 })).toBe(500);
  });

  it("使用默认 base/max", () => {
    // base=1000, max=30000；attempt=0 → 500
    expect(backoffDelay(0)).toBe(500);
  });

  it("jitter=1 时延迟落到 exp 上界", () => {
    vi.spyOn(Math, "random").mockReturnValue(1);
    // attempt=2, base=1000 → exp=4000, half=2000, delay = round(2000 + 2000*1) = 4000
    expect(backoffDelay(2, { base: 1000, max: 30000 })).toBe(4000);
  });

  it("100 次抽样均落在 [exp/2, exp] 区间内", () => {
    vi.restoreAllMocks();
    for (let i = 0; i < 100; i++) {
      const d = backoffDelay(3, { base: 1000, max: 30000 });
      // exp=8000, 区间 [4000, 8000]，round 后允许 ±1 抖动
      expect(d).toBeGreaterThanOrEqual(4000);
      expect(d).toBeLessThanOrEqual(8000);
    }
  });
});
