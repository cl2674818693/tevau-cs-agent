import ReactMarkdown from "react-markdown";
import { useTranslation } from "react-i18next";
import remarkGfm from "remark-gfm";

import { cn } from "../lib/utils";
import type { Message } from "../types";
import { Avatar, AvatarFallback } from "./ui/avatar";
import { ToolCallChip } from "./ToolCallChip";

export function MessageBubble({ m, userType = "b" }: { m: Message; userType?: "c" | "b" }) {
  const { t } = useTranslation();
  if (m.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded bg-brand text-ink-primary px-3 py-2 text-body1 whitespace-pre-wrap">
          {m.content}
        </div>
      </div>
    );
  }
  if (m.role === "system") {
    return (
      <div className="mx-auto max-w-[90%] text-center text-ink-secondary text-body3">
        {m.content}
      </div>
    );
  }
  if (m.role === "human_agent") {
    return (
      <div className="flex gap-2 items-start">
        <Avatar>
          <AvatarFallback className="bg-status-warning text-white">
            {t("chat.agentAvatar")}
          </AvatarFallback>
        </Avatar>
        <div className="flex-1 max-w-[80%] rounded-lg bg-yellow-50 border border-status-warning/30 px-page py-block-sm">
          <div className="text-footnote text-ink-secondary mb-0.5">
            {t("chat.agentBadge", { name: m.display_name ?? "" })}
          </div>
          <div className="text-body1 text-ink-primary whitespace-pre-wrap">{m.content}</div>
        </div>
      </div>
    );
  }
  // assistant
  return (
    <div className="flex gap-2 items-start">
      <Avatar>
        <AvatarFallback>AI</AvatarFallback>
      </Avatar>
      <div
        className={cn(
          "flex-1 max-w-[80%] rounded-lg bg-surface-card border border-line",
          "px-page py-block-sm space-y-2",
        )}
      >
        {(m.tool_calls ?? []).map((tc, i) => (
          <ToolCallChip key={i} tc={tc} userType={userType} />
        ))}
        <div className="markdown-body">
          {m.content ? (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
          ) : (
            <span className="text-ink-secondary text-body2">{t("chat.thinking")}</span>
          )}
        </div>
      </div>
    </div>
  );
}
