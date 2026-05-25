/**
 * 指数退避 + equal jitter（避免大量客户端断线后同时重连压垮服务端）。
 * 第 attempt 次（从 0 起）重试的延迟落在 [exp/2, exp]，exp = min(max, base * 2^attempt)。
 */
export function backoffDelay(attempt: number, opts: { base?: number; max?: number } = {}): number {
  const base = opts.base ?? 1000;
  const max = opts.max ?? 30000;
  const exp = Math.min(max, base * 2 ** Math.max(0, attempt));
  const half = exp / 2;
  return Math.round(half + Math.random() * half);
}
