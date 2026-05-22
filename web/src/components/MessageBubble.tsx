import { BadgeCheck } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { Message } from "../types";
import { Avatar, AvatarFallback } from "./ui/avatar";
import { ToolCallChip } from "./ToolCallChip";

export function MessageBubble({ m, userType = "b" }: { m: Message; userType?: "c" | "b" }) {
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
            客
          </AvatarFallback>
        </Avatar>
        <div className="flex-1 max-w-[85%]">
          <div className="flex items-center gap-1.5 mb-1 px-1">
            <span className="text-footnote font-bold text-chat-accent">
              客服 {m.display_name ?? ""}
            </span>
            <BadgeCheck className="h-3 w-3 text-chat-accent/80" />
            <span className="text-footnote text-chat-on-surface-variant/60">· 已认证</span>
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
            <span className="text-chat-on-surface-variant text-body2">思考中…</span>
          )}
        </div>
      </div>
    </div>
  );
}
