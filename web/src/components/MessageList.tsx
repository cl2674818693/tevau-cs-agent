import { useEffect, useRef } from "react";

import type { Message } from "../types";
import { MessageBubble } from "./MessageBubble";

export function MessageList({
  messages,
  userType = "b",
}: {
  messages: Message[];
  userType?: "c" | "b";
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // 可选链方法调用：jsdom 测试环境无 scrollTo
    ref.current?.scrollTo?.({ top: ref.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  return (
    <div ref={ref} className="flex-1 overflow-y-auto px-page py-block-lg flex flex-col gap-5">
      {messages.map((m, i) => (
        <MessageBubble key={i} m={m} userType={userType} />
      ))}
    </div>
  );
}
