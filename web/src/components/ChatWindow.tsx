import { sendTicketUserEvent } from "../api/chat";
import { userType } from "../api/identity";
import i18n from "../i18n";
import { useChat } from "../hooks/useChat";
import { useTicketStream } from "../hooks/useTicketStream";
import { useKeyboardInset } from "../hooks/useVisualViewport";
import { ChatHeader, ErrorView, LoadingView, StatusBanners, Suggestions } from "./ChatExtras";
import { HandoffButton } from "./HandoffButton";
import { InputBox } from "./InputBox";
import { MessageList } from "./MessageList";
import { TicketCard } from "./TicketCard";
import { TicketStatusBanner } from "./TicketStatusBanner";

type TicketStatus = "pending" | "assigned" | "in_progress" | "resolved" | "closed";

function inputPlaceholder(rateLimited: boolean, mode: string): string {
  if (rateLimited) return i18n.t("chat.inputRateLimited");
  if (mode === "human_takeover") return i18n.t("chat.inputHumanMode");
  return i18n.t("chat.inputPlaceholder");
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
        summary={ticket.comment ?? i18n.t("ticket.cardSummaryFallback")}
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

  return (
    <div
      className="mx-auto flex h-full max-w-[720px] flex-col bg-page-gradient"
      style={{ paddingBottom: inset }}
    >
      <ChatHeader mode={mode} staffName={chat.staffName} sending={sending} onStop={chat.stop} />

      <StatusBanners connection={chat.connection} limitPct={chat.limitPct} />
      <TicketStatusBanner events={ticketEvents} />
      <MessageList messages={messages} userType={isC ? "c" : "b"} />

      <TicketCardSlot ticket={latestTicket} mode={mode} />

      {onlyGreeting && isAi && <Suggestions onPick={send} />}

      {isAi && <HandoffButton onClick={chat.requestHandoff} disabled={sending} />}
      <InputBox
        onSend={send}
        disabled={sending || chat.rateLimited}
        placeholder={inputPlaceholder(chat.rateLimited, mode)}
      />
    </div>
  );
}
