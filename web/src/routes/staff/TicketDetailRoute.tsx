import {
  Alert,
  Breadcrumb,
  Button,
  Card,
  Flex,
  Skeleton,
  Tabs,
  Typography,
} from "antd";
import { format } from "date-fns";
import { useEffect, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";

import { getTicketDetail, type TicketDetail } from "../../api/adminTickets";
import { getConversationMessages, type StaffMessage } from "../../api/staff";
import { EventBubble, messageToStreamEvent } from "../../components/EventBubble";
import { useAsyncData } from "../../hooks/useAsyncData";
import { useStaffSession } from "../../hooks/useStaffSession";

// payload 内可能出现的 ISO 时间字段（带 T + 时区/微秒），统一格式化为列表页一致的 "YYYY-MM-DD HH:mm:ss"。
function formatValue(v: unknown): ReactNode {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "object") {
    return (
      <pre
        style={{
          margin: 0,
          padding: 8,
          background: "rgba(0,0,0,0.03)",
          borderRadius: 4,
          fontSize: 11,
          lineHeight: 1.5,
          whiteSpace: "pre-wrap",
          wordBreak: "break-all",
        }}
      >
        {JSON.stringify(v, null, 2)}
      </pre>
    );
  }
  if (typeof v === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/.test(v)) {
    try {
      return format(new Date(v), "yyyy-MM-dd HH:mm:ss");
    } catch {
      return v;
    }
  }
  return String(v);
}

const { Title, Text } = Typography;

function OverviewTab({
  t,
  loading,
}: {
  t: TicketDetail | null;
  loading: boolean;
}) {
  if (loading) {
    return (
      <Card size="small">
        <Skeleton active paragraph={{ rows: 4 }} />
      </Card>
    );
  }
  if (!t) return null;

  let payload: Record<string, unknown> = {};
  try {
    payload = JSON.parse(t.payload_json) as Record<string, unknown>;
  } catch {
    payload = {};
  }

  const rows: [string, ReactNode][] = [
    ["严重度", t.current_severity ?? "—"],
    ["创建时间", t.created_at],
    ...(Object.keys(payload).length > 0
      ? Object.entries(payload).map(
          ([k, v]) => [k, formatValue(v)] as [string, ReactNode],
        )
      : ([["payload", "（空）"]] as [string, ReactNode][])),
  ];

  // 同 BU 24h 内复用工单时后端只 append 事件不改 payload，概览里看到的 evidence 永远是首次那次的。
  // 顶部明确告诉客服"还有 N 次追加，去事件流看新 evidence"，避免照着旧卡号查歪。
  const appendCount = t.events.filter((e) => e.event === "evidence_added").length;

  return (
    <Card size="small">
      {appendCount > 0 && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 12 }}
          title={`本工单已被追加 ${appendCount} 次证据，下方 evidence 为首次创建时内容，最新追加请见「事件流」tab`}
        />
      )}
      <dl style={{ margin: 0, display: "flex", flexDirection: "column", gap: 8 }}>
        {rows.map(([label, value]) => (
          <div key={label} style={{ display: "flex", flexWrap: "wrap", gap: 12, fontSize: 12 }}>
            <dt
              style={{
                width: 96,
                flexShrink: 0,
                color: "rgba(0,0,0,0.45)",
                margin: 0,
              }}
            >
              {label}
            </dt>
            <dd style={{ margin: 0, flex: 1, minWidth: 0 }}>{value}</dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}

// evidence_added 事件 raw_json 解出来的载荷：上层只关心这三个字段是否存在，未知字段忽略而非报错。
function parseEventRaw(raw: string | null): {
  category?: string;
  severity?: string;
  evidence?: Record<string, unknown>;
} | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    return {
      category: typeof parsed.category === "string" ? parsed.category : undefined,
      severity: typeof parsed.severity === "string" ? parsed.severity : undefined,
      evidence:
        parsed.evidence && typeof parsed.evidence === "object"
          ? (parsed.evidence as Record<string, unknown>)
          : undefined,
    };
  } catch {
    return null;
  }
}

function EventsTab({
  events,
  loading,
}: {
  events: TicketDetail["events"];
  loading: boolean;
}) {
  if (loading) {
    return (
      <div className="flex flex-col gap-2">
        {[1, 2, 3].map((i) => (
          <Card key={i} size="small">
            <Skeleton active paragraph={{ rows: 1 }} />
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {events.length === 0 && (
        <Text type="secondary" style={{ display: "block", textAlign: "center", padding: 16, fontSize: 12 }}>
          暂无事件
        </Text>
      )}
      {events.map((e, i) => {
        // 追加证据事件：把 raw_json 里的 category/severity/evidence 展开渲染，
        // 否则客服只能看到 comment 一行字、看不到这次追加的新卡号 / 新订单号。
        const raw = e.event === "evidence_added" ? parseEventRaw(e.raw_json) : null;
        return (
          <Card key={i} size="small">
            <Flex justify="space-between" wrap="wrap" gap="small" style={{ fontSize: 12 }}>
              <Text strong>{e.event}</Text>
              <Text type="secondary" style={{ fontSize: 10 }}>
                {e.created_at}
              </Text>
            </Flex>
            {(e.actor || e.comment) && (
              <div style={{ marginTop: 4, fontSize: 10, color: "rgba(0,0,0,0.45)" }}>
                {e.actor && <span>执行人：{e.actor}</span>}
                {e.actor && e.comment && <span style={{ margin: "0 4px" }}>·</span>}
                {e.comment && <span>{e.comment}</span>}
              </div>
            )}
            {raw && (
              <div style={{ marginTop: 8, fontSize: 11 }}>
                {(raw.category || raw.severity) && (
                  <div style={{ color: "rgba(0,0,0,0.55)", marginBottom: 4 }}>
                    {raw.category && <span>分类：{raw.category}</span>}
                    {raw.category && raw.severity && <span style={{ margin: "0 6px" }}>·</span>}
                    {raw.severity && <span>严重度：{raw.severity}</span>}
                  </div>
                )}
                {raw.evidence && Object.keys(raw.evidence).length > 0 && (
                  <div>
                    <div style={{ color: "rgba(0,0,0,0.45)", marginBottom: 4 }}>追加证据：</div>
                    {formatValue(raw.evidence)}
                  </div>
                )}
              </div>
            )}
          </Card>
        );
      })}
    </div>
  );
}

function ConversationsTab({
  t,
  loading,
  token,
}: {
  t: TicketDetail | null;
  loading: boolean;
  token: string | null;
}) {
  const convId = t?.conversation_id ?? null;
  const [messages, setMessages] = useState<StaffMessage[]>([]);
  const [msgLoading, setMsgLoading] = useState(false);
  const [msgErr, setMsgErr] = useState("");

  useEffect(() => {
    if (!token || convId == null) {
      setMessages([]);
      return;
    }
    setMsgLoading(true);
    setMsgErr("");
    getConversationMessages(token, convId, { limit: 50 })
      .then((p) => setMessages(p.messages))
      .catch(() => setMsgErr("消息加载失败"))
      .finally(() => setMsgLoading(false));
  }, [token, convId]);

  if (loading || !t) {
    return (
      <Card size="small">
        <Skeleton active paragraph={{ rows: 3 }} />
      </Card>
    );
  }

  return (
    <div className="flex flex-col" style={{ gap: 12 }}>
      <Flex align="center" wrap="wrap" gap="small" style={{ fontSize: 12 }}>
        <Text type="secondary">会话 ID</Text>
        <Text strong>#{t.conversation_id}</Text>
        <Link
          to={`/staff/conversations/${t.conversation_id}/logs`}
          style={{ marginLeft: "auto" }}
        >
          查看完整日志
        </Link>
      </Flex>

      {msgErr && <Alert type="error" showIcon message={msgErr} />}

      {msgLoading && (
        <Card size="small">
          <Skeleton active paragraph={{ rows: 4 }} />
        </Card>
      )}

      {!msgLoading && !msgErr && messages.length === 0 && (
        <Text type="secondary" style={{ textAlign: "center", padding: 16, fontSize: 12 }}>
          无消息记录
        </Text>
      )}

      {!msgLoading &&
        messages.map((m) => {
          const ev = messageToStreamEvent(m);
          if (!ev) return null;
          const isRight = ev.type !== "user_message";
          return (
            <div key={m.id} className="flex flex-col" style={{ gap: 2 }}>
              <EventBubble ev={ev} convId={t.conversation_id} token={token} />
              <div
                style={{
                  fontSize: 10,
                  color: "rgba(0,0,0,0.45)",
                  paddingLeft: isRight ? 0 : 40,
                  paddingRight: isRight ? 40 : 0,
                  textAlign: isRight ? "right" : "left",
                }}
              >
                {m.created_at}
              </div>
            </div>
          );
        })}
    </div>
  );
}

export function TicketDetailRoute() {
  const { externalId = "" } = useParams();
  const { token } = useStaffSession();

  const {
    data: t,
    loading,
    error,
  } = useAsyncData(
    () => (token ? getTicketDetail(token, externalId) : null),
    [token, externalId],
    "工单加载失败",
  );

  return (
    <div className="space-y-4 p-6">
      <Breadcrumb
        items={[
          { title: <Link to="/staff">工作台</Link> },
          { title: <Link to="/staff/tickets">工单</Link> },
          { title: <span style={{ fontWeight: 500 }}>{externalId}</span> },
        ]}
      />

      <Flex justify="space-between" align="flex-start" wrap="wrap" gap="middle">
        <Title level={3} style={{ margin: 0 }}>
          工单 — {externalId}
        </Title>
        <Link to="/staff/tickets">
          <Button>返回工单列表</Button>
        </Link>
      </Flex>

      {error && <Alert type="error" showIcon title={error} />}

      <Tabs
        defaultActiveKey="overview"
        items={[
          {
            key: "overview",
            label: "概览",
            children: <OverviewTab t={t} loading={loading} />,
            // 强制渲染：让非激活 tab 也在 DOM，便于一进入页面就完成数据预热 +
            // 让测试断言能查到 events / conversations 面板内容
            forceRender: true,
          },
          {
            key: "events",
            label: "事件流",
            children: <EventsTab events={t?.events ?? []} loading={loading} />,
            forceRender: true,
          },
          {
            key: "conversations",
            label: "关联会话",
            children: <ConversationsTab t={t} loading={loading} token={token} />,
            forceRender: true,
          },
        ]}
      />
    </div>
  );
}
