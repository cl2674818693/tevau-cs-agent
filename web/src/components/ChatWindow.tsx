import { useChat } from "../hooks/useChat";
import { useTicketStream } from "../hooks/useTicketStream";
import { useKeyboardInset } from "../hooks/useVisualViewport";
import { HandoffButton } from "./HandoffButton";
import { InputBox } from "./InputBox";
import { MessageList } from "./MessageList";
import { TicketStatusBanner } from "./TicketStatusBanner";

export function ChatWindow() {
  const { messages, sending, send, requestHandoff, stop, init } = useChat();
  const ticketEvents = useTicketStream(init?.conversation_id ?? null);
  const inset = useKeyboardInset();

  return (
    <div
      className="mx-auto flex h-full max-w-[720px] flex-col bg-page-gradient"
      style={{ paddingBottom: inset }}
    >
      <header className="safe-top sticky top-0 z-10 flex items-center px-page py-3 bg-surface-card border-b border-line">
        <div className="h-7 w-7 rounded bg-brand grid place-items-center mr-2">
          <span className="text-ink-primary text-body0 font-bold">T</span>
        </div>
        <div className="flex-1">
          <div className="text-sh3 text-ink-primary">Tevau AI 客服</div>
          <div className="text-footnote text-ink-secondary">由 AI 驱动 · 复杂问题转人工</div>
        </div>
        {sending && (
          <button onClick={stop} className="text-body2 text-ink-secondary px-2">
            停止生成
          </button>
        )}
      </header>
      <TicketStatusBanner events={ticketEvents} />
      <MessageList messages={messages} />
      <HandoffButton onClick={requestHandoff} disabled={sending} />
      <InputBox onSend={send} disabled={sending} />
    </div>
  );
}
