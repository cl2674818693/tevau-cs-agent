import { sendTicketUserEvent } from "../api/chat";
import { userType } from "../api/identity";
import { useChat } from "../hooks/useChat";
import { useTicketStream } from "../hooks/useTicketStream";
import { useKeyboardInset } from "../hooks/useVisualViewport";
import { ChatHeader, EmptyState, ErrorView, LoadingView, StatusBanners } from "./ChatExtras";
import { HandoffPrompt } from "./HandoffButton";
import { InputBox } from "./InputBox";
import { MessageList } from "./MessageList";
import { TicketCard } from "./TicketCard";
import { TicketStatusBanner } from "./TicketStatusBanner";

type TicketStatus = "pending" | "assigned" | "in_progress" | "resolved" | "closed";

function inputPlaceholder(rateLimited: boolean, mode: string): string {
  if (rateLimited) return "请求过于频繁，请稍后再试…";
  if (mode === "human_takeover") return "向客服留言…";
  return "描述你的问题…";
}

function TicketCardSlot({
  ticket,
  mode,
}: {
  ticket?: { external_id?: string; event: string; comment?: string };
  mode: string;
}) {
  if (!ticket?.external_id || ticket.event === "closed" || mode !== "ai") return null;
  const send = (resolved: boolean) =>
    void sendTicketUserEvent(
      ticket.external_id!,
      resolved ? "user_confirmed_resolved" : "user_rejected_resolved",
    );
  return (
    <div className="px-page pb-2">
      <TicketCard
        externalId={ticket.external_id}
        summary={ticket.comment ?? "您的工单进展"}
        status={ticket.event as TicketStatus}
        onConfirm={() => send(true)}
        onReject={() => send(false)}
      />
    </div>
  );
}

export function ChatWindow() {
  const chat = useChat();
  const { messages, sending, mode, send, init } = chat;
  const ticketEvents = useTicketStream(init?.conversation_id ?? null);
  const inset = useKeyboardInset();
  const isC = userType() === "c";

  if (chat.status === "loading") return <LoadingView />;
  if (chat.status === "error") return <ErrorView onRetry={chat.retryInit} />;

  const latestTicket = ticketEvents[ticketEvents.length - 1];
  const onlyGreeting = messages.length <= 1;
  const isAi = mode === "ai";
  const greeting = (messages[0]?.role === "system" && messages[0].content) || "";
  // 按需转人工：AI 模式、对话已开始、未在生成时，于消息流末尾给一个克制入口
  //（无后端建议信号，纯前端呈现规则）。
  const showHandoff = isAi && !onlyGreeting && !sending;

  return (
    <div
      className="mx-auto flex h-full max-w-[720px] flex-col bg-surface-page text-ink"
      style={{ paddingBottom: inset }}
    >
      <ChatHeader mode={mode} staffName={chat.staffName} sending={sending} onStop={chat.stop} />

      <StatusBanners connection={chat.connection} limitPct={chat.limitPct} />
      <TicketStatusBanner events={ticketEvents} />

      {onlyGreeting && isAi ? (
        <EmptyState greeting={greeting} />
      ) : (
        <MessageList messages={messages} userType={isC ? "c" : "b"} />
      )}

      <TicketCardSlot ticket={latestTicket} mode={mode} />

      {showHandoff && <HandoffPrompt onClick={chat.requestHandoff} disabled={sending} />}

      <InputBox
        onSend={send}
        disabled={sending || chat.rateLimited}
        placeholder={inputPlaceholder(chat.rateLimited, mode)}
      />
    </div>
  );
}
