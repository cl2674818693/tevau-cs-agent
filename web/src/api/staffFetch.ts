import { clearStaffToken } from "../hooks/useStaffSession";

// 多个并发请求可能同时收到 401，只处理一次，避免重复跳转 / 抖动。
let handled = false;

/** 客服 token 失效（任一 staff/admin 请求返回 401）：清本地 token + 跳登录页。
 * 用硬跳转（window.location）而非 router.navigate：整页重载可重置所有 React 态与
 * 残留的 SSE 流，落到登录页时 useStaffSession 自然读不到 token。 */
function onStaffAuthExpired() {
  if (handled) return;
  handled = true;
  clearStaffToken();
  // 已在登录页（如登录请求自身 401）则不重复跳，避免刷掉错误提示。
  if (!window.location.pathname.endsWith("/staff/login")) {
    window.location.href = "/staff/login";
  }
}

/** 包装 fetch：staff/admin 接口 token 失效（401）时自动登出。其余行为与 fetch 一致，
 * 调用方仍按原样判断 r.ok / 解析 body。登录接口本身不要用它（401=账密错误，非会话过期）。 */
export async function staffFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const r = await fetch(input, init);
  if (r.status === 401) onStaffAuthExpired();
  return r;
}
