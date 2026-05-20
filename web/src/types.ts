// SSE 事件类型，对齐 spec §3.3 表
export type ChatEvent = {
  _eventId?: string; // 来自 SSE 的 id: 字段，用于断线重连 Last-Event-ID
} & (
  | { type: "conversation"; conversation_id: number; user_type: "c" | "b"; model: string }
  | { type: "message_start"; message_id: string }
  | { type: "content_block_delta"; index: number; delta: { type: "text_delta"; text: string } }
  | { type: "tool_use"; tool_use_id?: string; name: string; input: Record<string, unknown> }
  | { type: "tool_result"; tool_use_id?: string; name: string; is_error: boolean }
  | { type: "message_stop"; stop_reason: string; usage?: Record<string, unknown> }
  | { type: "ticket_event"; [k: string]: unknown }
  | { type: "mode_change"; from?: string; to: string; by_staff_id?: string }
  | { type: "transferred"; to_staff_id: string }
  | { type: "request_human"; ticket_id?: string }
  | {
      type: "human_message";
      message_id?: string;
      sender_staff_id?: string;
      display_name?: string;
      content: string;
    }
  | { type: "assistant_message"; content: string }
  | { type: "error"; code: string; message: string; retry_after_ms?: number }
  | { type: "warning"; pct?: number }
);

// 会话初始化端点响应（spec §6.2）
export type ConversationInit = {
  conversation_id: number;
  user_type: "c" | "b";
  display_name: string;
  greeting: string;
  history_url: string | null;
  limits: { daily_token_used_pct: number; max_turns: number };
};

export type Message =
  | { role: "system"; content: string }
  | { role: "user"; content: string }
  | { role: "assistant"; content: string; tool_calls?: ToolCallShown[] }
  | { role: "human_agent"; content: string; display_name?: string };

export type ConversationMode = "ai" | "human_pending" | "human_takeover" | "ai_draft";

export type ToolCallShown = {
  name: string;
  input: Record<string, unknown>;
  ok?: boolean;
};
