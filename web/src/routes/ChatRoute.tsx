import { useEffect, useState } from "react";

import { AgentRatingButton } from "../components/AgentRatingButton";
import { ChatWindow } from "../components/ChatWindow";
import { loadResumeContext } from "../lib/chatSession";

/** C 端 webview / B 端浏览器对话页。 */
export function ChatRoute() {
  // 从 chatSession 读上次续接的 conversation_id，供满意度采集按钮判断 eligibility。
  // 新建会话（resume 为 undefined）时按钮不会显示——人工接管发生前本来也不该弹评分。
  const [convId, setConvId] = useState<number | null>(null);
  useEffect(() => {
    let cancelled = false;
    loadResumeContext()
      .then((ctx) => {
        if (!cancelled && ctx.resume != null) setConvId(ctx.resume);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);
  return (
    <>
      <ChatWindow />
      <AgentRatingButton conversationId={convId} />
    </>
  );
}
