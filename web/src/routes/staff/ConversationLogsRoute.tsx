import {
  Alert,
  Breadcrumb,
  Button,
  Card,
  Flex,
  Skeleton,
  Tabs,
  Tag,
  Typography,
} from "antd";
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
import { useAsyncData } from "../../hooks/useAsyncData";
import { useStaffSession } from "../../hooks/useStaffSession";

const { Title, Text } = Typography;

const MSG_PAGE = 50;

/** 消息行状态徽章 */
function MsgBadges({ m }: { m: StaffMessage }) {
  return (
    <>
      {m.status === "failed" && (
        <Tag color="red" style={{ marginLeft: 8 }}>
          failed:{m.error_code ?? "-"}
        </Tag>
      )}
      {m.status === "processing" && (
        <Tag style={{ marginLeft: 8 }}>processing</Tag>
      )}
      {m.topic_verdict && m.topic_verdict !== "yes" && (
        <Tag style={{ marginLeft: 8 }}>verdict:{m.topic_verdict}</Tag>
      )}
    </>
  );
}

/** 长文本截断展开（纯 details，无依赖） */
function ExpandableText({ text, maxLen = 300 }: { text: string; maxLen?: number }) {
  if (text.length <= maxLen) {
    return (
      <span style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
        {text}
      </span>
    );
  }
  return (
    <details className="group">
      <summary
        style={{
          cursor: "pointer",
          userSelect: "none",
          listStyle: "none",
          color: "rgba(0,0,0,0.45)",
        }}
      >
        <span className="group-open:hidden">{text.slice(0, maxLen)}…（点击展开）</span>
        <span className="hidden group-open:inline">收起</span>
      </summary>
      <span style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
        {text}
      </span>
    </details>
  );
}

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
    getConversationMessages(token, convId, {
      limit: MSG_PAGE,
      beforeId: messages[0].id,
    })
      .then((p) => {
        setMessages((prev) => [...p.messages, ...prev]);
        setHasMore(p.hasMore);
      })
      .catch(() => setErr("加载更多失败"))
      .finally(() => setLoadingMore(false));
  };

  return { messages, hasMore, loading, loadingMore, err, loadEarlier };
}

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
  if (loading) {
    return (
      <div className="flex flex-col gap-2">
        {[1, 2, 3].map((i) => (
          <Card key={i} size="small">
            <Skeleton active paragraph={{ rows: 2 }} />
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {hasMore && (
        <Flex justify="center">
          <Button onClick={loadEarlier} loading={loadingMore}>
            加载更早消息
          </Button>
        </Flex>
      )}
      {messages.map((m) => (
        <Card key={m.id} size="small">
          <Flex wrap="wrap" align="center" style={{ fontSize: 10, color: "rgba(0,0,0,0.45)", marginBottom: 4 }}>
            <Text strong style={{ textTransform: "capitalize" }}>
              {m.role}
            </Text>
            <span style={{ margin: "0 4px" }}>·</span>
            <span>{m.created_at}</span>
            <MsgBadges m={m} />
          </Flex>
          <div style={{ fontSize: 12, fontWeight: 600 }}>
            <ExpandableText text={m.content} />
          </div>
          {m.attachments?.length ? (
            <Flex wrap="wrap" gap="small" style={{ marginTop: 8 }}>
              {m.attachments.map((a) => (
                <ImageThumb key={a.id} src={staffAttachmentUrl(convId, a.id)} />
              ))}
            </Flex>
          ) : null}
        </Card>
      ))}
      {messages.length === 0 && (
        <Text type="secondary" style={{ textAlign: "center", padding: 16, fontSize: 12 }}>
          无消息记录
        </Text>
      )}
    </div>
  );
}

function AuditsTab({ audits, loading }: { audits: ToolAudit[]; loading: boolean }) {
  if (loading) {
    return (
      <div className="flex flex-col gap-2">
        {[1, 2].map((i) => (
          <Card key={i} size="small">
            <Skeleton active paragraph={{ rows: 1 }} />
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {audits.map((a) => (
        <Card key={a.id} size="small">
          <Flex wrap="wrap" align="center" gap="small" style={{ fontSize: 12, marginBottom: 4 }}>
            <Text strong>{a.tool_name}</Text>
            <Text type="secondary">{a.duration_ms}ms</Text>
            <span style={{ color: a.is_empty === 1 || a.is_empty === true ? "#dc2626" : "rgba(0,0,0,0.45)" }}>
              返回 {a.result_count ?? 0} 条
            </span>
            {a.subject_id ? (
              <Text type="secondary">身份 {a.subject_id}</Text>
            ) : null}
            {a.rejected ? (
              <Tag color="red">被拒：{a.reject_reason ?? "-"}</Tag>
            ) : (
              <Tag color="green">ok</Tag>
            )}
          </Flex>
          {a.params_json && (
            <div style={{ marginTop: 4, fontSize: 10, color: "rgba(0,0,0,0.45)" }}>
              <ExpandableText text={a.params_json} maxLen={200} />
            </div>
          )}
          <div style={{ marginTop: 2, fontSize: 10, color: "rgba(0,0,0,0.45)" }}>
            {a.created_at}
          </div>
        </Card>
      ))}
      {audits.length === 0 && (
        <Text type="secondary" style={{ textAlign: "center", padding: 16, fontSize: 12 }}>
          无工具调用记录
        </Text>
      )}
    </div>
  );
}

function FeedbackTab({ feedback, loading }: { feedback: MessageFeedback[]; loading: boolean }) {
  if (loading) {
    return (
      <Card size="small">
        <Skeleton active paragraph={{ rows: 1 }} />
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {feedback.map((f) => (
        <Card key={f.id} size="small">
          <Flex wrap="wrap" align="center" gap="small" style={{ fontSize: 12 }}>
            <span
              style={{ color: f.rating === "down" ? "#dc2626" : "#059669" }}
              aria-label={f.rating === "down" ? "thumbs down" : "thumbs up"}
            >
              {f.rating === "down" ? "👎" : "👍"}
            </span>
            <Text type="secondary">消息 #{f.message_id}</Text>
            {f.reason ? <span>{f.reason}</span> : null}
            <span
              style={{
                marginLeft: "auto",
                fontSize: 10,
                color: "rgba(0,0,0,0.45)",
              }}
            >
              {f.created_at}
            </span>
          </Flex>
        </Card>
      ))}
      {feedback.length === 0 && (
        <Text type="secondary" style={{ textAlign: "center", padding: 16, fontSize: 12 }}>
          无用户反馈
        </Text>
      )}
    </div>
  );
}

export function ConversationLogsRoute() {
  const { id } = useParams();
  const convId = Number(id);
  const { token } = useStaffSession();

  const { messages, hasMore, loading, loadingMore, err: msgErr, loadEarlier } =
    useConversationMessages(token, convId);

  const { data: extra, loading: extraLoading } = useAsyncData(
    () =>
      token
        ? Promise.all([
            getConversationAudits(token, convId),
            getConversationFeedback(token, convId),
          ])
        : null,
    [token, convId],
  );
  const [audits, feedback] = extra ?? [[], []];

  return (
    <div className="space-y-4 p-6">
      <Breadcrumb
        items={[
          { title: <Link to="/staff/conversations">会话</Link> },
          { title: <Link to={`/staff/conversations/${convId}`}>#{convId}</Link> },
          { title: <span style={{ fontWeight: 500 }}>日志</span> },
        ]}
      />

      <Flex justify="space-between" align="flex-start" wrap="wrap" gap="middle">
        <Title level={3} style={{ margin: 0 }}>
          会话日志 — #{convId}
        </Title>
        <Link to={`/staff/conversations/${convId}`}>
          <Button>返回会话</Button>
        </Link>
      </Flex>

      {msgErr && <Alert type="error" showIcon title={msgErr} />}

      <Tabs
        defaultActiveKey="messages"
        items={[
          {
            key: "messages",
            label: "消息流",
            children: (
              <MessagesTab
                convId={convId}
                messages={messages}
                hasMore={hasMore}
                loading={loading}
                loadingMore={loadingMore}
                loadEarlier={loadEarlier}
              />
            ),
          },
          {
            key: "audits",
            label: "工具调用",
            children: <AuditsTab audits={audits as ToolAudit[]} loading={extraLoading} />,
          },
          {
            key: "feedback",
            label: "反馈",
            children: <FeedbackTab feedback={feedback as MessageFeedback[]} loading={extraLoading} />,
          },
        ]}
      />
    </div>
  );
}
