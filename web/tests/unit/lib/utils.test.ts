// cn() 是 clsx + tailwind-merge 的薄包装；只验合并/去重行为，不验底层细节。
import { describe, expect, it } from "vitest";

import { cn } from "@/lib/utils";

describe("cn 类名合并", () => {
  it("拼接多参数", () => {
    expect(cn("a", "b")).toBe("a b");
  });

  it("falsy 值自动剔除", () => {
    expect(cn("a", false, null, undefined, "", "b")).toBe("a b");
  });

  it("数组与对象语法", () => {
    expect(cn(["a", "b"], { c: true, d: false })).toBe("a b c");
  });

  it("tailwind 冲突后者覆盖前者", () => {
    expect(cn("p-2", "p-4")).toBe("p-4");
    expect(cn("text-red-500", "text-blue-500")).toBe("text-blue-500");
  });

  it("非冲突 tailwind 类全部保留", () => {
    expect(cn("flex", "items-center", "gap-2")).toBe("flex items-center gap-2");
  });

  it("空输入返回空串", () => {
    expect(cn()).toBe("");
  });
});
