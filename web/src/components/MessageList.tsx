import { useLayoutEffect, useRef } from "react";
import { useTranslation } from "react-i18next";

import type { Message } from "../types";
import { MessageBubble } from "./MessageBubble";

export function MessageList({
  messages,
  userType = "b",
  onFeedback,
  urlFor,
}: {
  messages: Message[];
  userType?: "c" | "b";
  onFeedback?: (messageIndex: number, rating: "up" | "down") => void;
  urlFor?: (attachmentId: number) => string;
}) {
  const { t } = useTranslation();
  const ref = useRef<HTMLDivElement>(null);
  const didInitialScroll = useRef(false);
  // useLayoutEffect：在 paint 前定位，刷新/恢复历史时不会先闪一下顶部再跳。
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    // 首次有内容（刷新/历史回灌是一次性大跳）瞬时贴底；smooth 动画在大跳+高度仍在变时
    // 常落在中途，故首屏用 auto 硬贴底，后续新消息再用 smooth 跟随。
    const behavior: ScrollBehavior = didInitialScroll.current ? "smooth" : "auto";
    el.scrollTo?.({ top: el.scrollHeight, behavior }); // 可选链：jsdom 测试环境无 scrollTo
    if (messages.length > 0) didInitialScroll.current = true;
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
          urlFor={urlFor}
          onFeedback={
            m.role === "assistant" && onFeedback ? (rating) => onFeedback(i, rating) : undefined
          }
        />
      ))}
    </div>
  );
}
