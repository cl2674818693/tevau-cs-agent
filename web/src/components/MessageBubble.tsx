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
        <div className="max-w-[80%] rounded-lg rounded-tr-sm bg-brand text-ink-onbrand px-4 py-2.5 text-body1 font-medium whitespace-pre-wrap">
          {m.content}
        </div>
      </div>
    );
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
    return (
      <div className="flex gap-3 items-start">
        <Avatar className="rounded-sm h-7 w-7">
          <AvatarFallback className="rounded-sm bg-soft-warning text-status-warning font-bold">
            客
          </AvatarFallback>
        </Avatar>
        <div className="flex-1 max-w-[85%]">
          <div className="flex items-center gap-1.5 mb-1 px-1">
            <span className="text-footnote font-bold text-status-warning">
              客服 {m.display_name ?? ""}
            </span>
            <BadgeCheck className="h-3 w-3 text-status-warning" />
            <span className="text-footnote text-ink-secondary">· 已认证</span>
          </div>
          <div className="bg-soft-warning border border-status-warning/30 rounded-lg rounded-tl-sm px-4 py-2.5 text-body1 text-ink whitespace-pre-wrap">
            {m.content}
          </div>
        </div>
      </div>
    );
  }
  // assistant
  return (
    <div className="flex gap-3 items-start">
      <Avatar className="rounded-sm h-7 w-7">
        <AvatarFallback className="rounded-sm bg-brand text-ink-onbrand font-bold">T</AvatarFallback>
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
            <span className="text-ink-secondary text-body2">思考中…</span>
          )}
        </div>
      </div>
    </div>
  );
}
