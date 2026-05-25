import { Headphones } from "lucide-react";
import { useTranslation } from "react-i18next";

/**
 * 内联「转人工」行动条。由 ChatWindow 在 AI 模式、对话已开始时渲染于消息流末尾。
 * 点击调 useChat.requestHandoff → POST /request-human（spec §13.7）。
 */
export function HandoffPrompt({ onClick, disabled }: { onClick: () => void; disabled: boolean }) {
  const { t } = useTranslation();
  return (
    <div className="flex justify-center px-page pb-1">
      <button
        onClick={onClick}
        disabled={disabled}
        className="inline-flex items-center gap-1.5 py-1.5 px-3 rounded-full text-body3 text-ink-secondary transition-colors hover:text-brand hover:bg-soft-brand disabled:opacity-40"
      >
        <Headphones className="h-3.5 w-3.5" />
        {t("chat.handoff")}
      </button>
    </div>
  );
}
