import {
  Alert,
  Button,
  Card,
  Flex,
  Input,
  Segmented,
  Skeleton,
  Switch,
  Table,
  Tag,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { listStaffConversations } from "../../api/staff";
import type { StaffConversation } from "../../api/staff";
import { useAsyncData } from "../../hooks/useAsyncData";
import { useStaffSession } from "../../hooks/useStaffSession";

const { Title } = Typography;

const FILTER_OPTIONS: { value: string; label: string }[] = [
  { value: "human_pending", label: "待人工" },
  { value: "human_takeover", label: "人工接管" },
  { value: "all", label: "全部" },
  { value: "risk", label: "有风险信号" },
];

const MODE_LABEL: Record<string, string> = {
  ai: "AI 对话",
  ai_draft: "AI 草稿",
  human_pending: "等待人工",
  human_takeover: "人工接管",
};

const MODE_COLOR: Record<string, string> = {
  ai: "default",
  ai_draft: "purple",
  human_pending: "orange",
  human_takeover: "blue",
};

// 风险角标：变量驱动，按真值显示（兼容 boolean / 0|1）
// 列表里风险只是提示，不是 alert，用 antd Tag 的色阶传达严重程度。
const RISK_BADGES: {
  key: keyof StaffConversation;
  label: string;
  color: string;
}[] = [
  { key: "has_failed", label: "失败", color: "red" },
  { key: "has_downvote", label: "差评", color: "red" },
  { key: "has_out_of_scope", label: "范围外", color: "orange" },
  { key: "has_empty_tool", label: "空结果", color: "default" },
  { key: "needs_review", label: "待复核", color: "blue" },
];

export function ConversationsListRoute() {
  const { token, role, staffId } = useStaffSession();
  const canSpectate = role === "senior" || role === "engineer";
  const [status, setStatus] = useState<string>("human_pending");
  const [myOnly, setMyOnly] = useState(false);
  const [search, setSearch] = useState("");

  // "有风险信号"：服务端不另设 status，按全部范围 + risk_only 过滤
  const riskOnly = status === "risk";
  const apiStatus = riskOnly ? "all" : status;
  const { data, loading, error } = useAsyncData(
    () => (token ? listStaffConversations(token, apiStatus, riskOnly) : null),
    [token, apiStatus, riskOnly],
    "加载失败",
  );

  const rawItems = data ?? [];
  const items = myOnly
    ? rawItems.filter((c) => c.assigned_staff_id === staffId)
    : rawItems;

  const columns: ColumnsType<StaffConversation> = useMemo(
    () => [
      {
        title: "会话 ID",
        dataIndex: "id",
        width: 100,
        sorter: (a, b) => a.id - b.id,
        render: (id: number) => (
          <Link
            to={`/staff/conversations/${id}`}
            style={{ fontFamily: "ui-monospace, monospace", fontSize: 12 }}
          >
            #{id}
          </Link>
        ),
      },
      {
        title: "用户类型",
        dataIndex: "user_type",
        width: 100,
        render: (v: string) => (
          <span style={{ fontSize: 12 }}>{v === "c" ? "C 端用户" : "BU"}</span>
        ),
      },
      {
        title: "Subject",
        dataIndex: "subject_id",
        render: (v: string) => (
          <span
            style={{
              fontFamily: "ui-monospace, monospace",
              fontSize: 12,
              color: "rgba(0,0,0,0.65)",
            }}
          >
            {v}
          </span>
        ),
      },
      {
        title: "模式",
        dataIndex: "mode",
        width: 140,
        render: (v: string) => (
          <Tag color={MODE_COLOR[v] ?? "default"}>{MODE_LABEL[v] ?? v}</Tag>
        ),
      },
      {
        title: "负责人",
        dataIndex: "assigned_staff_id",
        width: 120,
        render: (v: string | null) => (
          <span
            style={{
              fontFamily: "ui-monospace, monospace",
              fontSize: 12,
              color: "rgba(0,0,0,0.65)",
            }}
          >
            {v ?? "—"}
          </span>
        ),
      },
      {
        title: "风险",
        key: "risk_flags",
        render: (_: unknown, row: StaffConversation) => {
          const badges = RISK_BADGES.filter((b) => !!row[b.key]);
          if (badges.length === 0)
            return <span style={{ color: "rgba(0,0,0,0.45)" }}>—</span>;
          return (
            <Flex wrap="wrap" gap={4}>
              {badges.map((b) => (
                <Tag key={b.key} color={b.color}>
                  {b.label}
                </Tag>
              ))}
            </Flex>
          );
        },
      },
      {
        title: "",
        key: "actions",
        width: 140,
        render: (_: unknown, row: StaffConversation) => (
          <Flex gap="small">
            <Link to={`/staff/conversations/${row.id}/logs`}>
              <Button type="link" size="small" style={{ padding: 0 }}>
                日志
              </Button>
            </Link>
            {canSpectate && (
              <Link to={`/staff/conversations/${row.id}/spectate`}>
                <Button type="link" size="small" style={{ padding: 0 }}>
                  旁观
                </Button>
              </Link>
            )}
          </Flex>
        ),
      },
    ],
    [canSpectate],
  );

  const filteredItems = useMemo(() => {
    const kw = search.trim().toLowerCase();
    return kw
      ? items.filter((c) => c.subject_id.toLowerCase().includes(kw))
      : items;
  }, [items, search]);

  return (
    <div className="space-y-4 p-6">
      <Title level={3} style={{ margin: 0 }}>
        会话
      </Title>

      <Flex wrap="wrap" align="center" gap="middle">
        <Segmented value={status} onChange={setStatus} options={FILTER_OPTIONS} />
        <Flex align="center" gap="small">
          <Switch checked={myOnly} onChange={setMyOnly} />
          <span style={{ fontSize: 13 }}>我负责的</span>
        </Flex>
      </Flex>

      {error && <Alert type="error" showIcon title={error} />}

      {loading ? (
        <Card>
          <Skeleton active paragraph={{ rows: 5 }} />
        </Card>
      ) : (
        <Card>
          <Flex style={{ marginBottom: 12 }}>
            <Input.Search
              placeholder="搜索 Subject ID…"
              allowClear
              style={{ width: 240 }}
              onChange={(e) => setSearch(e.target.value)}
            />
          </Flex>
          <Table<StaffConversation>
            rowKey="id"
            size="middle"
            columns={columns}
            dataSource={filteredItems}
            pagination={{ pageSize: 20, showSizeChanger: true }}
            locale={{ emptyText: "暂无会话" }}
            scroll={{ x: "max-content" }}
          />
        </Card>
      )}
    </div>
  );
}
