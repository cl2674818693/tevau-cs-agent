import { Avatar } from "antd";
import { BadgeCheck } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import ReactMarkdown from "react-markdown";

import { safeMarkdownProps } from "@/lib/markdown-safe";

import type { Attachment, Message } from "../types";

import { ImageThumb } from "./ImageThumb";

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

/** 内容含 CJK 走中文，否则英文。让反馈条等"伴随 UI"跟随 AI 回复语言。 */
const HAS_CJK = /[㐀-鿿]/;
function langOf(text: string): "zh" | "en" {
  return HAS_CJK.test(text) ? "zh" : "en";
}

/** AI 回复下方的 👍/👎 反馈条。点过一次即锁定并显示致谢。 */
function FeedbackBar({
  onFeedback,
  lng,
}: {
  onFeedback: (rating: "up" | "down") => void;
  lng: "zh" | "en";
}) {
  const { t } = useTranslation();
  const [done, setDone] = useState(false);
  if (done)
    return (
      <div className="text-footnote text-ink-secondary">{t("chat.feedbackThanks", { lng })}</div>
    );
  const click = (rating: "up" | "down") => {
    setDone(true);
    onFeedback(rating);
  };
  const up = t("chat.feedbackUp", { lng });
  const down = t("chat.feedbackDown", { lng });
  return (
    <div className="flex gap-3 text-footnote text-ink-secondary">
      <button type="button" aria-label={up} onClick={() => click("up")}>
        👍 {up}
      </button>
      <button type="button" aria-label={down} onClick={() => click("down")}>
        👎 {down}
      </button>
    </div>
  );
}

type UrlFor = ((attachmentId: number) => string) | undefined;

/** 用户气泡：右对齐，图片在上、文字气泡在下（纯图片时不渲染空气泡）。 */
function UserBubble({ content, attachments, urlFor }: { content: string; attachments?: Attachment[]; urlFor: UrlFor }) {
  return (
    <div className="flex justify-end">
      <div className="min-w-0 max-w-[80%] flex flex-col items-end gap-1">
        <Attachments attachments={attachments} urlFor={urlFor} />
        {content && (
          <div className="rounded-lg rounded-tr-sm bg-brand text-ink-onbrand px-4 py-2.5 text-body1 font-medium whitespace-pre-wrap [overflow-wrap:anywhere]">
            {content}
          </div>
        )}
      </div>
    </div>
  );
}

type HumanAgentMsg = Extract<Message, { role: "human_agent" }>;

/** 客服气泡：✓ 已认证 标识 + 文字气泡 + 附件。
 *  头像内容用 "T"（与 AI 统一），底色保留橙（区分 AI/客服 来源）；
 *  不展示客服 display_name，避免暴露员工花名/真名给用户。 */
function HumanAgentBubble({ m, urlFor }: { m: HumanAgentMsg; urlFor: UrlFor }) {
  const { t } = useTranslation();
  return (
    <div className="flex gap-3 items-start">
      <Avatar
        shape="square"
        size={28}
        style={{ background: "var(--soft-warning, #fff7ed)", color: "var(--status-warning, #d97706)", fontWeight: 700 }}
      >
        T
      </Avatar>
      <div className="flex-1 max-w-[85%]">
        <div className="flex items-center gap-1.5 mb-1 px-1">
          <BadgeCheck className="h-3 w-3 text-status-warning" />
          <span className="text-footnote text-ink-secondary">{t("chat.agentVerified")}</span>
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
      <Avatar
        shape="square"
        size={28}
        style={{ background: "var(--brand, #4f46e5)", color: "#fff", fontWeight: 700 }}
      >
        T
      </Avatar>
      <div className="flex-1 min-w-0 max-w-[85%] bg-surface-card border border-line shadow-sm rounded-lg rounded-tl-sm px-4 py-3 space-y-2">
        <div className="markdown-body-dark">
          {m.content ? (
            <ReactMarkdown
              {...safeMarkdownProps}
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
        {m.content && onFeedback && <FeedbackBar onFeedback={onFeedback} lng={langOf(m.content)} />}
      </div>
    </div>
  );
}
