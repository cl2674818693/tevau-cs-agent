import { attachmentUrl, uploadAttachment } from "../api/attachments";
import { sendFeedback, sendTicketUserEvent } from "../api/chat";
import { userType } from "../api/identity";
import type { ConversationInit } from "../types";
import i18n from "../i18n";
import { useChat } from "../hooks/useChat";
import { useTicketStream } from "../hooks/useTicketStream";
import { useKeyboardInset } from "../hooks/useVisualViewport";
import { AgentRatingPromptToast } from "./AgentRatingPromptToast";
import {
  ChatHeader,
  EmptyState,
  ErrorView,
  GuestLoginBar,
  LoadingView,
  StatusBanners,
} from "./ChatExtras";
import { HandoffPrompt } from "./HandoffButton";
import { InputBox } from "./InputBox";
import { MessageList } from "./MessageList";
import { TicketCard } from "./TicketCard";
import { TicketStatusBanner } from "./TicketStatusBanner";
import type { Message } from "../types";

type TicketStatus = "pending" | "assigned" | "in_progress" | "resolved" | "closed";

function inputPlaceholder(rateLimited: boolean, mode: string): string {
  if (rateLimited) return i18n.t("chat.inputRateLimited");
  // human_pending：用户已转人工等候，输入框语义化成"留言区"，让用户知道写下去是补充给客服、
  // 不要期待 AI 立即响应（spec §13 这种 mode 下后端不调 AI）。human_takeover 同理。
  if (mode === "human_takeover" || mode === "human_pending") return i18n.t("chat.inputHumanMode");
  return i18n.t("chat.inputPlaceholder");
}

/** AI 模式、对话已开始、未在生成时才给转人工入口（纯前端呈现规则，无后端建议信号）。 */
function shouldShowHandoff(mode: string, msgCount: number, sending: boolean): boolean {
  return mode === "ai" && msgCount > 1 && !sending;
}

/** 空状态（仅欢迎语 + AI 模式）→ 居中欢迎；否则消息流。 */
function ChatBody({
  messages,
  mode,
  userType,
  onFeedback,
  urlFor,
}: {
  messages: Message[];
  mode: string;
  userType: "c" | "b";
  onFeedback?: (i: number, rating: "up" | "down") => void;
  urlFor?: (attachmentId: number) => string;
}) {
  if (messages.length <= 1 && mode === "ai") {
    const greeting = messages[0]?.role === "system" ? messages[0].content : "";
    return <EmptyState greeting={greeting} />;
  }
  return (
    <MessageList
      messages={messages}
      userType={userType}
      onFeedback={onFeedback}
      urlFor={urlFor}
    />
  );
}

function ChatRatingPrompt({
  init,
  ticketEvents,
}: {
  init: ConversationInit | null;
  ticketEvents: import("../hooks/useTicketStream").TicketEvent[];
}) {
  return (
    <AgentRatingPromptToast
      convId={init ? init.conversation_id : null}
      ticketEvents={ticketEvents}
    />
  );
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

/** 反馈回调：init 就绪才返回处理函数（把分支挪出组件主体，控制圈复杂度）。 */
function feedbackHandler(init: ConversationInit | null) {
  if (!init) return undefined;
  return (i: number, rating: "up" | "down") => void sendFeedback(init.conversation_id, i, rating);
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
  const showHandoff = shouldShowHandoff(mode, messages.length, sending);

  return (
    <div
      // 作为 top-level 路由自己声明视口高度（对齐 SpectateRoute h-screen / 登录页 min-h-screen
      // 的全局模式），不再依赖 #root → .ant-app → 这里的 h-full 链路；
      // 键盘弹起时 inset = innerHeight - visualViewport.height，与 100vh 语义匹配。
      className="mx-auto flex h-screen max-w-[720px] flex-col bg-surface-page text-ink md:my-6 md:h-[calc(100vh-3rem)] md:rounded-2xl md:border md:border-line md:bg-surface-card md:shadow-lg md:overflow-hidden"
      style={{ paddingBottom: inset }}
    >
      <ChatHeader
        mode={mode}
        staffName={chat.staffName}
        sending={sending}
        onStop={chat.stop}
        userType={isC ? "c" : "b"}
      />

      <StatusBanners connection={chat.connection} limitPct={chat.limitPct} />
      {init?.user_type === "g" && <GuestLoginBar />}
      <TicketStatusBanner events={ticketEvents} />

      <ChatBody
        messages={messages}
        mode={mode}
        userType={isC ? "c" : "b"}
        onFeedback={feedbackHandler(init)}
        urlFor={init ? (id) => attachmentUrl(init.conversation_id, id) : undefined}
      />

      <TicketCardSlot ticket={latestTicket} mode={mode} />

      <ChatRatingPrompt init={init} ticketEvents={ticketEvents} />

      {showHandoff && <HandoffPrompt onClick={chat.requestHandoff} disabled={sending} />}

      <InputBox
        onSend={send}
        disabled={sending || chat.rateLimited}
        placeholder={inputPlaceholder(chat.rateLimited, mode)}
        upload={init ? (f) => uploadAttachment(init.conversation_id, f) : undefined}
      />
    </div>
  );
}
