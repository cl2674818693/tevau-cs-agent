import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = { children: ReactNode; fallback?: ReactNode };
type State = { hasError: boolean };

/**
 * 全局错误边界：任一子树渲染抛错时兜底展示，避免整页白屏。
 * React 错误边界只能是 class 组件。
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // 控制台保留堆栈，便于线上排障（后续可接入前端监控上报）
    console.error("UI crashed:", error, info.componentStack);
  }

  private handleReload = (): void => {
    window.location.reload();
  };

  render(): ReactNode {
    if (!this.state.hasError) return this.props.children;
    if (this.props.fallback !== undefined) return this.props.fallback;
    return (
      <div
        role="alert"
        className="flex min-h-screen flex-col items-center justify-center gap-4 p-6 text-center"
      >
        <p className="text-lg font-semibold text-slate-800">页面出错了</p>
        <p className="text-sm text-slate-500">请刷新页面重试。若反复出现，请联系客服。</p>
        <button
          type="button"
          onClick={this.handleReload}
          className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
        >
          刷新页面
        </button>
      </div>
    );
  }
}
