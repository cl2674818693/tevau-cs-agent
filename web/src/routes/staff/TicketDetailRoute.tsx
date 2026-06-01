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
import type { ReactNode } from "react";
import { Link, useParams } from "react-router-dom";

import { getTicketDetail, type TicketDetail } from "../../api/adminTickets";
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

  return (
    <Card size="small">
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
      {events.map((e, i) => (
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
        </Card>
      ))}
    </div>
  );
}

function ConversationsTab({
  t,
  loading,
}: {
  t: TicketDetail | null;
  loading: boolean;
}) {
  if (loading) {
    return (
      <Card size="small">
        <Skeleton active paragraph={{ rows: 1 }} />
      </Card>
    );
  }
  if (!t) return null;

  return (
    <Card size="small">
      <Flex align="center" wrap="wrap" gap="small" style={{ fontSize: 12 }}>
        <Text type="secondary">会话 ID</Text>
        <Link
          to={`/staff/conversations/${t.conversation_id}/logs`}
          style={{ fontWeight: 500 }}
        >
          #{t.conversation_id}
        </Link>
      </Flex>
    </Card>
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
            children: <ConversationsTab t={t} loading={loading} />,
            forceRender: true,
          },
        ]}
      />
    </div>
  );
}
