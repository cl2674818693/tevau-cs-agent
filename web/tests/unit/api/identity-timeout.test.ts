/** F-P0-2: bridge.getToken hang 时 authHeaders 必须在 timeout 内降级为游客。
 *
 * 现场：某些 APP 版本 bridge 实现 bug 会让 callHandler('getToken') 永不 resolve；
 * 旧实现直接 await，整个 chat 请求被无限挂起。修复：authHeaders 内对 getToken
 * 套 Promise.race timeout，超时按未登录处理。
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { authHeaders, setIdentity, _setGetTokenTimeoutForTest } from "@/api/identity";

describe("authHeaders timeout protection", () => {
  beforeEach(() => {
    _setGetTokenTimeoutForTest(50); // 50ms 便于测试
  });
  afterEach(() => {
    _setGetTokenTimeoutForTest(null); // 还原
  });

  it("getToken hang 永不 resolve → 50ms 后降级 X-Guest-ID", async () => {
    setIdentity({
      kind: "c",
      getToken: () => new Promise(() => {}), // 永不 resolve
    });
    const start = Date.now();
    const headers = await authHeaders();
    const elapsed = Date.now() - start;
    expect(elapsed).toBeLessThan(500);
    expect(headers.Authorization).toBeUndefined();
    expect(headers["X-Guest-ID"]).toBeDefined();
  });

  it("getToken 正常 resolve 时返回 Bearer", async () => {
    setIdentity({
      kind: "c",
      getToken: async () => "tok-real",
    });
    const headers = await authHeaders();
    expect(headers.Authorization).toBe("Bearer tok-real");
    expect(headers["X-Guest-ID"]).toBeUndefined();
  });
});
