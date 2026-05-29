import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { staffAttachmentUrl } from "../../api/attachments";
import {
  getConversationAudits,
  getConversationFeedback,
  getConversationMessages,
  type StaffMessage,
} from "../../api/staff";
import { ImageThumb } from "../../components/ImageThumb";
import { Alert } from "../../components/ui/alert";
import { Badge } from "../../components/ui/badge";
import { Card } from "../../components/ui/card";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { useAsyncData } from "../../hooks/useAsyncData";
import { useStaffSession } from "../../hooks/useStaffSession";

const MSG_PAGE = 50;

/** 消息行的状态/判定徽章（失败、范围外判定等留痕信号）。 */
function MsgBadges({ m }: { m: StaffMessage }) {
  return (
    <>
      {m.status === "failed" && (
        <Badge variant="error" className="ml-2">
          failed:{m.error_code ?? "-"}
        </Badge>
      )}
      {m.status === "processing" && (
        <Badge variant="pending" className="ml-2">
          processing
        </Badge>
      )}
      {m.topic_verdict && m.topic_verdict !== "yes" && (
        <Badge variant="neutral" className="ml-2">
          verdict:{m.topic_verdict}
        </Badge>
      )}
    </>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-4 first:mt-2">
      <h3 className="mb-1 text-sh3 text-ink-primary">{title}</h3>
      <div className="flex flex-col gap-1">{children}</div>
    </section>
  );
}

/** 消息历史：分页加载（首屏最新一页，往上"加载更早"）。 */
function useConversationMessages(token: string | null, convId: number) {
  const [messages, setMessages] = useState<StaffMessage[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [err, setErr] = useState("");

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
      .catch(() => setErr("加载失败"))
      .finally(() => setLoadingMore(false));
  };

  return { messages, hasMore, loading, loadingMore, err, loadEarlier };
}

// eslint-disable-next-line max-lines-per-function -- 留痕详情页：会话消息(分页)+工具审计+反馈三段视图
export function ConversationLogsRoute() {
  const { id } = useParams();
  const convId = Number(id);
  const { token } = useStaffSession();

  const { messages, hasMore, loading, loadingMore, err, loadEarlier } = useConversationMessages(
    token,
    convId,
  );

  // 审计 + 反馈：一次性加载（条数受会话规模约束，无需分页）
  const { data: extra } = useAsyncData(
    () =>
      token
        ? Promise.all([getConversationAudits(token, convId), getConversationFeedback(token, convId)])
        : null,
    [token, convId],
  );
  const [audits, feedback] = extra ?? [[], []];

  return (
    <PageContainer width="wide">
      <PageHeader
        title={`会话 #${convId} 留痕`}
        actions={
          <Link to={`/staff/conversations/${convId}`} className="text-body3 text-ink-secondary">
            返回会话
          </Link>
        }
      />
      {err && (
        <Alert variant="error" className="mb-2">
          {err}
        </Alert>
      )}
      {loading ? (
        <LoadingState />
      ) : (
        <>
          <Section title="消息历史">
            {hasMore && (
              <button
                type="button"
                onClick={loadEarlier}
                disabled={loadingMore}
                className="self-center rounded border border-line px-3 py-1 text-body3 text-ink-secondary disabled:opacity-50"
              >
                {loadingMore ? "加载中…" : "加载更早消息"}
              </button>
            )}
            {messages.map((m) => (
              <Card key={m.id} className="px-3 py-2">
                <div className="text-footnote text-ink-secondary">
                  {m.role} · {m.created_at}
                  <MsgBadges m={m} />
                </div>
                <div className="whitespace-pre-wrap break-words text-body3 text-ink-primary">
                  {m.content}
                </div>
                {m.attachments?.length ? (
                  <div className="mt-1 flex flex-wrap gap-2">
                    {m.attachments.map((a) => (
                      <ImageThumb key={a.id} src={staffAttachmentUrl(convId, a.id)} />
                    ))}
                  </div>
                ) : null}
              </Card>
            ))}
            {messages.length === 0 && <div className="text-body3 text-ink-secondary">无消息</div>}
          </Section>

          <Section title="工具调用审计">
            {audits.map((a) => (
              <Card key={a.id} className="px-3 py-2 text-body3">
                <span className="text-ink-primary">{a.tool_name}</span>
                <span className="ml-2 text-ink-secondary">{a.duration_ms}ms</span>
                <span
                  className={
                    a.is_empty === 1 || a.is_empty === true
                      ? "ml-2 text-status-error"
                      : "ml-2 text-ink-secondary"
                  }
                >
                  返回 {a.result_count ?? 0} 条
                </span>
                {a.subject_id ? (
                  <span className="ml-2 text-ink-secondary">身份 {a.subject_id}</span>
                ) : null}
                {a.rejected ? (
                  <Badge variant="error" className="ml-2">
                    被拒：{a.reject_reason ?? "-"}
                  </Badge>
                ) : null}
                <div className="break-words text-footnote text-ink-secondary">{a.params_json}</div>
              </Card>
            ))}
            {audits.length === 0 && (
              <div className="text-body3 text-ink-secondary">无工具调用</div>
            )}
          </Section>

          <Section title="反馈">
            {feedback.map((f) => (
              <Card key={f.id} className="px-3 py-2 text-body3">
                <span className={f.rating === "down" ? "text-status-error" : "text-ink-primary"}>
                  {f.rating === "down" ? "👎" : "👍"}
                </span>
                <span className="ml-2 text-ink-secondary">msg #{f.message_id}</span>
                {f.reason ? <span className="ml-2 text-ink-primary">{f.reason}</span> : null}
              </Card>
            ))}
            {feedback.length === 0 && <div className="text-body3 text-ink-secondary">无反馈</div>}
          </Section>
        </>
      )}
    </PageContainer>
  );
}
