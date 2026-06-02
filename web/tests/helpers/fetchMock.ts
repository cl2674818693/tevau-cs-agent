// 路由级测试用的 fetch mock：注册 (method, predicate) → handler。
// - predicate 接 (pathname, search, request) → boolean
// - 字符串 predicate = "包含" 子串匹配（保留旧用法），但优先匹配"最长"那个
// - 未匹配请求返回 500，让用例显式排查
import { vi } from "vitest";

export type FetchHandler = (input: Request) => Response | Promise<Response>;
export type Predicate = string | RegExp | ((url: URL, req: Request) => boolean);

type Route = {
  method: string;
  predicate: Predicate;
  handler: FetchHandler;
  once: boolean;
};

let routes: Route[] = [];

function buildRequest(input: RequestInfo | URL, init?: RequestInit): Request {
  const url = typeof input === "string" || input instanceof URL ? input.toString() : input.url;
  return new Request(url.startsWith("http") ? url : `http://localhost${url}`, init);
}

function matchScore(pred: Predicate, url: URL, req: Request): number {
  if (typeof pred === "function") return pred(url, req) ? 1 : -1;
  const full = url.pathname + url.search;
  if (pred instanceof RegExp) return pred.test(full) ? full.length : -1;
  return full.includes(pred) ? pred.length : -1;
}

export function installFetch(): void {
  routes = [];
  const impl = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const req = buildRequest(input, init);
    const url = new URL(req.url);
    const method = req.method.toUpperCase();
    // 找最长（最具体）的匹配
    let bestIdx = -1;
    let bestScore = -1;
    for (let i = 0; i < routes.length; i++) {
      const r = routes[i];
      if (r.method !== method) continue;
      const s = matchScore(r.predicate, url, req);
      if (s > bestScore) {
        bestScore = s;
        bestIdx = i;
      }
    }
    if (bestIdx === -1) {
      // eslint-disable-next-line no-console
      console.warn(`[fetchMock] no handler for ${method} ${url.pathname}${url.search}`);
      return new Response("not mocked", { status: 500 });
    }
    const route = routes[bestIdx];
    if (route.once) routes.splice(bestIdx, 1);
    return route.handler(req);
  };
  // @ts-expect-error 覆盖全局 fetch
  globalThis.fetch = vi.fn(impl);
}

export function resetFetch(): void {
  routes = [];
}

export function mockFetch(
  method: string,
  predicate: Predicate,
  handler: FetchHandler,
  opts: { once?: boolean } = {},
): void {
  routes.push({ method: method.toUpperCase(), predicate, handler, once: !!opts.once });
}

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export function emptyResponse(status = 200): Response {
  return new Response(null, { status });
}

/** 返回一个永远 pending 的 Response（用于断言 loading 态）。 */
export function pendingResponse(): Promise<Response> {
  return new Promise<Response>(() => {
    /* never resolves */
  });
}
