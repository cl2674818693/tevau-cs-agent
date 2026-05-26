import { useEffect, useState, type DependencyList } from "react";

type AsyncState<T> = { data: T | null; loading: boolean; error: string };

/**
 * 统一数据页的拉取状态：loading/error/data。
 * - fn 返回 null 表示"无前置条件"（如未登录），此时不发起请求、保持非 loading。
 * - deps 变化重新拉取；组件卸载或 deps 变更后丢弃过期结果。
 */
export function useAsyncData<T>(
  fn: () => Promise<T> | null,
  deps: DependencyList,
  errorMsg = "加载失败",
): AsyncState<T> {
  const [state, setState] = useState<AsyncState<T>>({ data: null, loading: true, error: "" });

  useEffect(() => {
    const promise = fn();
    if (!promise) {
      setState({ data: null, loading: false, error: "" });
      return;
    }
    let cancelled = false;
    setState((s) => ({ ...s, loading: true, error: "" }));
    promise
      .then((data) => {
        if (!cancelled) setState({ data, loading: false, error: "" });
      })
      .catch(() => {
        if (!cancelled) setState({ data: null, loading: false, error: errorMsg });
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return state;
}
