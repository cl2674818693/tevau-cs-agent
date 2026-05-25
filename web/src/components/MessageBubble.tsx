import { BadgeCheck } from "lucide-react";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { useTranslation } from "react-i18next";
import remarkGfm from "remark-gfm";

import type { Message } from "../types";
import { Avatar, AvatarFallback } from "./ui/avatar";
import { ToolCallChip } from "./ToolCallChip";

/** AI 回复下方的 👍/👎 反馈条。点过一次即锁定并显示致谢。 */
function FeedbackBar({ onFeedback }: { onFeedback: (rating: "up" | "down") => void }) {
  const { t } = useTranslation();
  const [done, setDone] = useState(false);
  if (done)
    return <div className="text-footnote text-ink-secondary">{t("chat.feedbackThanks")}</div>;
  const click = (rating: "up" | "down") => {
    setDone(true);
    onFeedback(rating);
  };
  return (
    <div className="flex gap-3 text-footnote text-ink-secondary">
      <button type="button" aria-label={t("chat.feedbackUp")} onClick={() => click("up")}>
        👍 {t("chat.feedbackUp")}
      </button>
      <button type="button" aria-label={t("chat.feedbackDown")} onClick={() => click("down")}>
        👎 {t("chat.feedbackDown")}
      </button>
    </div>
  );
}

export function MessageBubble({
  m,
  userType = "b",
  onFeedback,
}: {
  m: Message;
  userType?: "c" | "b";
  onFeedback?: (rating: "up" | "down") => void;
}) {
  const { t } = useTranslation();
  if (m.role === "user") {
    return (
      <div className="flex justify-end">
        <div
          className="max-w-[80%] rounded-2xl rounded-tr-none bg-gradient-to-r from-[#0891B2] to-[#22D3EE] text-chat-on-primary px-4 py-3 text-body1 font-medium whitespace-pre-wrap"
          style={{ boxShadow: "0 4px 14px rgba(34,211,238,0.2)" }}
        >
          {m.content}
        </div>
      </div>
    );
  }
  if (m.role === "system") {
    return (
      <div className="flex justify-center">
        <span className="text-footnote text-chat-on-surface-variant/60 py-1 px-3 rounded-full bg-chat-surface-variant/30 border border-white/5">
          {m.content}
        </span>
      </div>
    );
  }
  if (m.role === "human_agent") {
    return (
      <div className="flex gap-3 items-start">
        <Avatar>
          <AvatarFallback className="bg-chat-accent/20 text-chat-accent font-bold border-2 border-chat-accent/40">
            {t("chat.agentAvatar")}
          </AvatarFallback>
        </Avatar>
        <div className="flex-1 max-w-[85%]">
          <div className="flex items-center gap-1.5 mb-1 px-1">
            <span className="text-footnote font-bold text-chat-accent">
              {t("chat.agentLabel")} {m.display_name ?? ""}
            </span>
            <BadgeCheck className="h-3 w-3 text-chat-accent/80" />
            <span className="text-footnote text-chat-on-surface-variant/60">
              · {t("chat.agentVerified")}
            </span>
          </div>
          <div className="glass amber-glow-border rounded-xl rounded-tl-none px-4 py-3 text-body1 text-chat-on-surface/90 whitespace-pre-wrap">
            {m.content}
          </div>
        </div>
      </div>
    );
  }
  // assistant
  return (
    <div className="flex gap-3 items-start">
      <Avatar>
        <AvatarFallback className="bg-chat-surface-variant text-chat-primary border-2 border-chat-primary/30">
          AI
        </AvatarFallback>
      </Avatar>
      <div className="flex-1 max-w-[85%] glass cyan-glow-border rounded-xl rounded-tl-none px-4 py-3 space-y-2">
        {(m.tool_calls ?? []).map((tc, i) => (
          <ToolCallChip key={i} tc={tc} userType={userType} />
        ))}
        <div className="markdown-body-dark text-chat-on-surface/90">
          {m.content ? (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
          ) : (
            <span className="text-chat-on-surface-variant text-body2">{t("chat.thinking")}</span>
          )}
        </div>
        {m.content && onFeedback && <FeedbackBar onFeedback={onFeedback} />}
      </div>
    </div>
  );
}
