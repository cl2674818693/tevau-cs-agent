import { afterEach, describe, expect, it, vi } from "vitest";

import { backoffDelay } from "../src/lib/backoff";

afterEach(() => vi.restoreAllMocks());

describe("backoffDelay", () => {
  it("第0次落在 [base/2, base]", () => {
    vi.spyOn(Math, "random").mockReturnValue(0);
    expect(backoffDelay(0, { base: 1000 })).toBe(500); // exp=1000, half=500, +0
    vi.spyOn(Math, "random").mockReturnValue(1);
    expect(backoffDelay(0, { base: 1000 })).toBe(1000); // half + half
  });

  it("随 attempt 指数增长", () => {
    vi.spyOn(Math, "random").mockReturnValue(0);
    expect(backoffDelay(1, { base: 1000 })).toBe(1000); // exp=2000, half=1000
    expect(backoffDelay(2, { base: 1000 })).toBe(2000); // exp=4000, half=2000
    expect(backoffDelay(3, { base: 1000 })).toBe(4000); // exp=8000, half=4000
  });

  it("封顶在 max", () => {
    vi.spyOn(Math, "random").mockReturnValue(1);
    expect(backoffDelay(20, { base: 1000, max: 30000 })).toBe(30000);
  });

  it("有抖动（同一 attempt 多次不全相等）", () => {
    const vals = new Set(Array.from({ length: 50 }, () => backoffDelay(3)));
    expect(vals.size).toBeGreaterThan(1);
  });
});
