import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";

import type { Message } from "../types";
import { MessageBubble } from "./MessageBubble";

export function MessageList({
  messages,
  userType = "b",
  onFeedback,
}: {
  messages: Message[];
  userType?: "c" | "b";
  onFeedback?: (messageIndex: number, rating: "up" | "down") => void;
}) {
  const { t } = useTranslation();
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // 可选链方法调用：jsdom 测试环境无 scrollTo
    ref.current?.scrollTo?.({ top: ref.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  return (
    <div
      ref={ref}
      // a11y：消息区作为实时日志，新消息（含 AI 流式回复）由读屏软件礼貌播报
      role="log"
      aria-live="polite"
      aria-label={t("chat.messageLog")}
      className="flex-1 overflow-y-auto px-page py-block-lg flex flex-col gap-5"
    >
      {messages.map((m, i) => (
        <MessageBubble
          key={i}
          m={m}
          userType={userType}
          onFeedback={
            m.role === "assistant" && onFeedback ? (rating) => onFeedback(i, rating) : undefined
          }
        />
      ))}
    </div>
  );
}
