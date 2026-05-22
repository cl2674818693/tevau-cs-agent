import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuthExpiredError, authHeaders, setIdentity } from "../src/api/identity";
import { ToolCallChip } from "../src/components/ToolCallChip";

afterEach(() => vi.restoreAllMocks());

describe("identity authHeaders", () => {
  it("B 端返回 X-BU-ID", async () => {
    setIdentity({ kind: "b", buId: "BU9" });
    expect(await authHeaders()).toEqual({ "X-BU-ID": "BU9" });
  });

  it("B 端无 buId（靠 cookie）返回空头", async () => {
    setIdentity({ kind: "b" });
    expect(await authHeaders()).toEqual({});
  });

  it("C 端返回 Bearer token", async () => {
    setIdentity({ kind: "c", getToken: async () => "jwt-xyz" });
    expect(await authHeaders()).toEqual({ Authorization: "Bearer jwt-xyz" });
  });

  it("C 端 token 缺失抛 AuthExpiredError", async () => {
    setIdentity({ kind: "c", getToken: async () => null });
    await expect(authHeaders()).rejects.toBeInstanceOf(AuthExpiredError);
  });
});

describe("ToolCallChip C/B 差异化（spec §6.2）", () => {
  const tc = { name: "query_card", input: { card_id: "C1" }, ok: true };

  it("C 端语言化，不暴露工具名/JSON", () => {
    render(<ToolCallChip tc={tc} userType="c" />);
    expect(screen.getByText("正在查询卡片状态…")).toBeTruthy();
    expect(screen.queryByText("query_card")).toBeNull();
  });

  it("B 端显示技术工具名", () => {
    render(<ToolCallChip tc={tc} userType="b" />);
    expect(screen.getByText("query_card")).toBeTruthy();
  });
});
