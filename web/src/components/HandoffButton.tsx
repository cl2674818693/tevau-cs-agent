import { useTranslation } from "react-i18next";

/**
 * "没解决？转人工 →" 按钮。点击调 useChat.requestHandoff →
 * POST /request-human（置 human_pending + 建人工介入工单，spec §13.7）。
 */
export function HandoffButton({ onClick, disabled }: { onClick: () => void; disabled: boolean }) {
  const { t } = useTranslation();
  return (
    <div className="px-page py-2 border-t border-line bg-surface-card">
      <button
        onClick={onClick}
        disabled={disabled}
        className="w-full text-body2 text-ink-secondary py-2 rounded border border-line hover:bg-surface-hover disabled:opacity-50"
      >
        {t("chat.handoff")}
      </button>
    </div>
  );
}
