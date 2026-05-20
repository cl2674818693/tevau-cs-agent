/**
 * "没解决？转人工 →" 按钮。MVP-1 不调 /request-human 端点（spec §13.7）——
 * 点击后由 useChat 发送固定 user message "我想转人工"，AI 通过 prompt 识别意图自动建工单。
 */
export function HandoffButton({ onClick, disabled }: { onClick: () => void; disabled: boolean }) {
  return (
    <div className="px-page py-2 border-t border-line bg-surface-card">
      <button
        onClick={onClick}
        disabled={disabled}
        className="w-full text-body2 text-ink-secondary py-2 rounded border border-line hover:bg-surface-hover disabled:opacity-50"
      >
        没解决？转人工 →
      </button>
    </div>
  );
}
