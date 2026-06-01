import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { staffAttachmentUrl } from "../../api/attachments";
import {
  getConversationAudits,
  getConversationFeedback,
  getConversationMessages,
  type MessageFeedback,
  type StaffMessage,
  type ToolAudit,
} from "../../api/staff";
import { ImageThumb } from "../../components/ImageThumb";
import { Alert } from "../../components/ui/alert";
import { Badge } from "../../components/ui/badge";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "../../components/ui/breadcrumb";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { Skeleton } from "../../components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../../components/ui/tabs";
import { useAsyncData } from "../../hooks/useAsyncData";
import { useStaffSession } from "../../hooks/useStaffSession";

const MSG_PAGE = 50;

// ─── helpers ──────────────────────────────────────────────────────────────────

/** 消息行状态徽章 */
function MsgBadges({ m }: { m: StaffMessage }) {
  return (
    <>
      {m.status === "failed" && (
        <Badge variant="destructive" className="ml-2">
          failed:{m.error_code ?? "-"}
        </Badge>
      )}
      {m.status === "processing" && (
        <Badge variant="secondary" className="ml-2">
          processing
        </Badge>
      )}
      {m.topic_verdict && m.topic_verdict !== "yes" && (
        <Badge variant="secondary" className="ml-2">
          verdict:{m.topic_verdict}
        </Badge>
      )}
    </>
  );
}

/** 长文本截断展开（纯 details，无依赖） */
function ExpandableText({ text, maxLen = 300 }: { text: string; maxLen?: number }) {
  if (text.length <= maxLen) {
    return <span className="whitespace-pre-wrap break-words">{text}</span>;
  }
  return (
    <details className="group">
      <summary className="cursor-pointer select-none list-none text-muted-foreground hover:text-foreground">
        <span className="group-open:hidden">{text.slice(0, maxLen)}…（点击展开）</span>
        <span className="hidden group-open:inline">收起</span>
      </summary>
      <span className="whitespace-pre-wrap break-words">{text}</span>
    </details>
  );
}

// ─── tab skeletons ─────────────────────────────────────────────────────────────

function MessagesSkeleton() {
  return (
    <div className="flex flex-col gap-2">
      {[1, 2, 3].map((i) => (
        <Card key={i} className="px-3 py-2">
          <Skeleton className="mb-2 h-3 w-40" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="mt-1 h-4 w-3/4" />
        </Card>
      ))}
    </div>
  );
}

function AuditsSkeleton() {
  return (
    <div className="flex flex-col gap-2">
      {[1, 2].map((i) => (
        <Card key={i} className="px-3 py-2">
          <Skeleton className="mb-2 h-3 w-32" />
          <Skeleton className="h-4 w-full" />
        </Card>
      ))}
    </div>
  );
}

function FeedbackSkeleton() {
  return (
    <div className="flex flex-col gap-2">
      {[1].map((i) => (
        <Card key={i} className="px-3 py-2">
          <Skeleton className="h-4 w-48" />
        </Card>
      ))}
    </div>
  );
}

// ─── message history (paginated) ──────────────────────────────────────────────

function useConversationMessages(token: string | null, convId: number) {
  const [messages, setMessages] = useState<StaffMessage[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [err, setErr] = useState("");

  // initial load
  useEffect(() => {
    if (!token) return;
    setLoading(true);
    getConversationMessages(token, convId, { limit: MSG_PAGE })
      .then((p) => {
        setMessages(p.messages);
        setHasMore(p.hasMore);
        setErr("");
      })
      .catch(() => setErr("加载失败"))
      .finally(() => setLoading(false));
  }, [token, convId]);

  const loadEarlier = () => {
    if (!token || messages.length === 0 || loadingMore) return;
    setLoadingMore(true);
    getConversationMessages(token, convId, { limit: MSG_PAGE, beforeId: messages[0].id })
      .then((p) => {
        setMessages((prev) => [...p.messages, ...prev]);
        setHasMore(p.hasMore);
      })
      .catch(() => setErr("加载更多失败"))
      .finally(() => setLoadingMore(false));
  };

  return { messages, hasMore, loading, loadingMore, err, loadEarlier };
}

// ─── tab panels ───────────────────────────────────────────────────────────────

function MessagesTab({
  convId,
  messages,
  hasMore,
  loading,
  loadingMore,
  loadEarlier,
}: {
  convId: number;
  messages: StaffMessage[];
  hasMore: boolean;
  loading: boolean;
  loadingMore: boolean;
  loadEarlier: () => void;
}) {
  if (loading) return <MessagesSkeleton />;

  return (
    <div className="flex flex-col gap-2">
      {hasMore && (
        <Button
          variant="outline"
          size="sm"
          onClick={loadEarlier}
          disabled={loadingMore}
          className="self-center"
        >
          {loadingMore ? "加载中…" : "加载更早消息"}
        </Button>
      )}
      {messages.map((m) => (
        <Card key={m.id} className="px-3 py-2">
          <div className="mb-1 flex flex-wrap items-center text-[10px] text-muted-foreground">
            <span className="font-medium capitalize">{m.role}</span>
            <span className="mx-1">·</span>
            <span>{m.created_at}</span>
            <MsgBadges m={m} />
          </div>
          <div className="text-xs font-semibold text-foreground">
            <ExpandableText text={m.content} />
          </div>
          {m.attachments?.length ? (
            <div className="mt-2 flex flex-wrap gap-2">
              {m.attachments.map((a) => (
                <ImageThumb key={a.id} src={staffAttachmentUrl(convId, a.id)} />
              ))}
            </div>
          ) : null}
        </Card>
      ))}
      {messages.length === 0 && (
        <div className="py-4 text-center text-xs text-muted-foreground">无消息记录</div>
      )}
    </div>
  );
}

function AuditsTab({ audits, loading }: { audits: ToolAudit[]; loading: boolean }) {
  if (loading) return <AuditsSkeleton />;

  return (
    <div className="flex flex-col gap-2">
      {audits.map((a) => (
        <Card key={a.id} className="px-3 py-2">
          <div className="mb-1 flex flex-wrap items-center gap-2 text-xs">
            <span className="font-medium text-foreground">{a.tool_name}</span>
            <span className="text-muted-foreground">{a.duration_ms}ms</span>
            <span
              className={
                a.is_empty === 1 || a.is_empty === true
                  ? "text-status-error"
                  : "text-muted-foreground"
              }
            >
              返回 {a.result_count ?? 0} 条
            </span>
            {a.subject_id ? (
              <span className="text-muted-foreground">身份 {a.subject_id}</span>
            ) : null}
            {a.rejected ? (
              <Badge variant="destructive">被拒：{a.reject_reason ?? "-"}</Badge>
            ) : (
              <Badge variant="success">ok</Badge>
            )}
          </div>
          {a.params_json && (
            <div className="mt-1 text-[10px] text-muted-foreground">
              <ExpandableText text={a.params_json} maxLen={200} />
            </div>
          )}
          <div className="mt-0.5 text-[10px] text-muted-foreground">{a.created_at}</div>
        </Card>
      ))}
      {audits.length === 0 && (
        <div className="py-4 text-center text-xs text-muted-foreground">无工具调用记录</div>
      )}
    </div>
  );
}

function FeedbackTab({ feedback, loading }: { feedback: MessageFeedback[]; loading: boolean }) {
  if (loading) return <FeedbackSkeleton />;

  return (
    <div className="flex flex-col gap-2">
      {feedback.map((f) => (
        <Card key={f.id} className="px-3 py-2">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span
              className={f.rating === "down" ? "text-status-error" : "text-status-success"}
              aria-label={f.rating === "down" ? "thumbs down" : "thumbs up"}
            >
              {f.rating === "down" ? "👎" : "👍"}
            </span>
            <span className="text-muted-foreground">消息 #{f.message_id}</span>
            {f.reason ? <span className="text-foreground">{f.reason}</span> : null}
            <span className="ml-auto text-[10px] text-muted-foreground">{f.created_at}</span>
          </div>
        </Card>
      ))}
      {feedback.length === 0 && (
        <div className="py-4 text-center text-xs text-muted-foreground">无用户反馈</div>
      )}
    </div>
  );
}

// ─── main route ───────────────────────────────────────────────────────────────

export function ConversationLogsRoute() {
  const { id } = useParams();
  const convId = Number(id);
  const { token } = useStaffSession();

  const { messages, hasMore, loading, loadingMore, err: msgErr, loadEarlier } =
    useConversationMessages(token, convId);

  // 审计 + 反馈：一次性加载（条数受会话规模约束）
  const { data: extra, loading: extraLoading } = useAsyncData(
    () =>
      token
        ? Promise.all([getConversationAudits(token, convId), getConversationFeedback(token, convId)])
        : null,
    [token, convId],
  );
  const [audits, feedback] = extra ?? [[], []];

  return (
    <PageContainer width="wide">
      {/* Breadcrumb */}
      <Breadcrumb className="mb-2">
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to="/staff/conversations">会话</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to={`/staff/conversations/${convId}`}>#{convId}</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>日志</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <PageHeader
        title={`会话日志 — #${convId}`}
        actions={
          <Button variant="outline" size="sm" asChild>
            <Link to={`/staff/conversations/${convId}`}>返回会话</Link>
          </Button>
        }
      />

      {msgErr && (
        <Alert variant="destructive" className="mb-3">
          {msgErr}
        </Alert>
      )}

      <Tabs defaultValue="messages" className="mt-1">
        <TabsList className="mb-3">
          <TabsTrigger value="messages">消息流</TabsTrigger>
          <TabsTrigger value="audits">工具调用</TabsTrigger>
          <TabsTrigger value="feedback">反馈</TabsTrigger>
        </TabsList>

        <TabsContent value="messages">
          <MessagesTab
            convId={convId}
            messages={messages}
            hasMore={hasMore}
            loading={loading}
            loadingMore={loadingMore}
            loadEarlier={loadEarlier}
          />
        </TabsContent>

        <TabsContent value="audits">
          <AuditsTab audits={audits as ToolAudit[]} loading={extraLoading} />
        </TabsContent>

        <TabsContent value="feedback">
          <FeedbackTab feedback={feedback as MessageFeedback[]} loading={extraLoading} />
        </TabsContent>
      </Tabs>
    </PageContainer>
  );
}
