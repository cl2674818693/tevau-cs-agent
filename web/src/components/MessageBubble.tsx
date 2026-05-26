import { BadgeCheck } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { Attachment, Message } from "../types";
import { ImageThumb } from "./ImageThumb";
import { ToolCallChip } from "./ToolCallChip";
import { Avatar, AvatarFallback } from "./ui/avatar";

/** 消息附件图片网格；urlFor 缺省时不渲染（无法拼出看图 URL）。 */
function Attachments({
  attachments,
  urlFor,
}: {
  attachments?: Attachment[];
  urlFor?: (attachmentId: number) => string;
}) {
  if (!attachments?.length || !urlFor) return null;
  return (
    <div className="flex flex-wrap gap-2 mt-1">
      {attachments.map((a) => (
        <ImageThumb key={a.id} src={urlFor(a.id)} />
      ))}
    </div>
  );
}

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

type UrlFor = ((attachmentId: number) => string) | undefined;

/** 用户气泡：右对齐，图片在上、文字气泡在下（纯图片时不渲染空气泡）。 */
function UserBubble({ content, attachments, urlFor }: { content: string; attachments?: Attachment[]; urlFor: UrlFor }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[80%] flex flex-col items-end gap-1">
        <Attachments attachments={attachments} urlFor={urlFor} />
        {content && (
          <div className="rounded-lg rounded-tr-sm bg-brand text-ink-onbrand px-4 py-2.5 text-body1 font-medium whitespace-pre-wrap">
            {content}
          </div>
        )}
      </div>
    </div>
  );
}

type HumanAgentMsg = Extract<Message, { role: "human_agent" }>;

/** 客服气泡：署名 + 已验证标识，文字气泡 + 附件。 */
function HumanAgentBubble({ m, urlFor }: { m: HumanAgentMsg; urlFor: UrlFor }) {
  const { t } = useTranslation();
  return (
    <div className="flex gap-3 items-start">
      <Avatar className="rounded-sm h-7 w-7">
        <AvatarFallback className="rounded-sm bg-soft-warning text-status-warning font-bold">
          {t("chat.agentAvatar")}
        </AvatarFallback>
      </Avatar>
      <div className="flex-1 max-w-[85%]">
        <div className="flex items-center gap-1.5 mb-1 px-1">
          <span className="text-footnote font-bold text-status-warning">
            {t("chat.agentLabel")} {m.display_name ?? ""}
          </span>
          <BadgeCheck className="h-3 w-3 text-status-warning" />
          <span className="text-footnote text-ink-secondary">· {t("chat.agentVerified")}</span>
        </div>
        {m.content && (
          <div className="bg-soft-warning border border-status-warning/30 rounded-lg rounded-tl-sm px-4 py-2.5 text-body1 text-ink whitespace-pre-wrap">
            {m.content}
          </div>
        )}
        <Attachments attachments={m.attachments} urlFor={urlFor} />
      </div>
    </div>
  );
}

export function MessageBubble({
  m,
  userType = "b",
  onFeedback,
  urlFor,
}: {
  m: Message;
  userType?: "c" | "b";
  onFeedback?: (rating: "up" | "down") => void;
  /** 把 attachment id 拼成看图 URL；用户侧用 attachmentUrl，客服侧用 staffAttachmentUrl。 */
  urlFor?: (attachmentId: number) => string;
}) {
  const { t } = useTranslation();
  if (m.role === "user") {
    return <UserBubble content={m.content} attachments={m.attachments} urlFor={urlFor} />;
  }
  if (m.role === "system") {
    return (
      <div className="flex justify-center">
        <span className="text-footnote text-ink-secondary py-1 px-3 rounded-full bg-surface-subtle">
          {m.content}
        </span>
      </div>
    );
  }
  if (m.role === "human_agent") {
    return <HumanAgentBubble m={m} urlFor={urlFor} />;
  }
  // assistant
  return (
    <div className="flex gap-3 items-start">
      <Avatar className="rounded-sm h-7 w-7">
        <AvatarFallback className="rounded-sm bg-brand text-ink-onbrand font-bold">
          T
        </AvatarFallback>
      </Avatar>
      <div className="flex-1 max-w-[85%] bg-surface-card border border-line shadow-sm rounded-lg rounded-tl-sm px-4 py-3 space-y-2">
        {(m.tool_calls ?? []).map((tc, i) => (
          <ToolCallChip key={i} tc={tc} userType={userType} />
        ))}
        <div className="markdown-body-dark">
          {m.content ? (
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                table: ({ node: _node, ...props }) => (
                  <div className="overflow-x-auto scrollbar-hide -mx-1 px-1">
                    <table {...props} />
                  </div>
                ),
              }}
            >
              {m.content}
            </ReactMarkdown>
          ) : (
            <span className="text-ink-secondary text-body2">{t("chat.thinking")}</span>
          )}
        </div>
        <Attachments attachments={m.attachments} urlFor={urlFor} />
        {m.content && onFeedback && <FeedbackBar onFeedback={onFeedback} />}
      </div>
    </div>
  );
}
