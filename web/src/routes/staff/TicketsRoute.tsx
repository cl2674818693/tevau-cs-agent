import {
  Alert,
  Button,
  Card,
  Flex,
  Input,
  Segmented,
  Skeleton,
  Space,
  Table,
  Tag,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { format } from "date-fns";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { listTickets, type Ticket, type TicketStatus } from "../../api/staff";
import { useStaffSession } from "../../hooks/useStaffSession";

const { Title } = Typography;

const PAGE_SIZE = 50;

const STATUS_META: Record<
  TicketStatus,
  { label: string; color: string }
> = {
  pending: { label: "待处理", color: "default" },
  in_progress: { label: "进行中", color: "blue" },
  resolved: { label: "已解决", color: "green" },
  closed: { label: "已关闭", color: "default" },
};

const SEVERITY_COLOR: Record<string, string> = {
  p0: "red",
  p1: "red",
  p2: "default",
  p3: "default",
};

function SeverityTag({ value }: { value: string | null }) {
  if (!value) return <span style={{ color: "rgba(0,0,0,0.45)" }}>—</span>;
  const v = value.toLowerCase();
  return (
    <Tag
      color={SEVERITY_COLOR[v] ?? "default"}
      style={{ fontFamily: "ui-monospace, monospace" }}
    >
      {value.toUpperCase()}
    </Tag>
  );
}

function formatDateTime(val: string) {
  try {
    return format(new Date(val), "yyyy-MM-dd HH:mm");
  } catch {
    return val;
  }
}

const STATUS_OPTIONS = [
  { value: "", label: "全部状态" },
  { value: "pending", label: "待处理" },
  { value: "in_progress", label: "进行中" },
  { value: "resolved", label: "已解决" },
  { value: "closed", label: "已关闭" },
];

const SEVERITY_FILTER_OPTIONS = [
  { value: "", label: "全部严重度" },
  { value: "p0", label: "P0" },
  { value: "p1", label: "P1" },
  { value: "p2", label: "P2" },
  { value: "p3", label: "P3" },
];

export function TicketsRoute() {
  const { token } = useStaffSession();
  const nav = useNavigate();

  const [status, setStatus] = useState<TicketStatus | "">("");
  const [severity, setSeverity] = useState("");
  const [rows, setRows] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [hasMore, setHasMore] = useState(false);
  const [search, setSearch] = useState("");

  const buildFilter = useCallback(
    (beforeId?: string) => ({
      open:
        status === ""
          ? undefined
          : status !== "closed" && status !== "resolved",
      severity: severity || undefined,
      beforeId,
      limit: PAGE_SIZE,
    }),
    [status, severity],
  );

  useEffect(() => {
    if (!token) {
      nav("/staff/login");
      return;
    }
    setLoading(true);
    setLoadError("");
    listTickets(token, buildFilter())
      .then((data) => {
        setRows(data);
        setHasMore(data.length >= PAGE_SIZE);
      })
      .catch(() => setLoadError("加载失败"))
      .finally(() => setLoading(false));
  }, [token, buildFilter, nav]);

  function loadMore() {
    if (!token || rows.length === 0) return;
    const lastId = rows[rows.length - 1].external_id;
    listTickets(token, buildFilter(lastId))
      .then((data) => {
        setRows((prev) => [...prev, ...data]);
        setHasMore(data.length >= PAGE_SIZE);
      })
      .catch(() => setLoadError("加载更多失败"));
  }

  const columns: ColumnsType<Ticket> = useMemo(
    () => [
      {
        title: "工单号",
        dataIndex: "external_id",
        sorter: (a, b) => a.external_id.localeCompare(b.external_id),
        render: (v: string) => (
          <Link
            to={`/staff/tickets/${v}`}
            style={{ fontFamily: "ui-monospace, monospace", fontSize: 12 }}
          >
            {v}
          </Link>
        ),
      },
      {
        title: "分类",
        dataIndex: "category",
        render: (v: string | null) =>
          v ?? <span style={{ color: "rgba(0,0,0,0.45)" }}>—</span>,
      },
      {
        title: "严重度",
        dataIndex: "severity",
        width: 100,
        render: (v: string | null) => <SeverityTag value={v} />,
      },
      {
        title: "状态",
        dataIndex: "status",
        width: 100,
        render: (s: TicketStatus) => {
          const meta = STATUS_META[s] ?? STATUS_META.in_progress;
          return <Tag color={meta.color}>{meta.label}</Tag>;
        },
      },
      {
        title: "创建时间",
        dataIndex: "created_at",
        width: 160,
        defaultSortOrder: "descend",
        sorter: (a, b) =>
          new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
        render: (v: string) => (
          <span
            style={{
              fontFamily: "ui-monospace, monospace",
              fontSize: 12,
              color: "rgba(0,0,0,0.65)",
              whiteSpace: "nowrap",
            }}
          >
            {formatDateTime(v)}
          </span>
        ),
      },
      {
        title: "关联会话",
        dataIndex: "conversation_id",
        width: 120,
        render: (id: number) => (
          <Link
            to={`/staff/conversations/${id}/logs`}
            style={{ fontFamily: "ui-monospace, monospace", fontSize: 12 }}
          >
            #{id}
          </Link>
        ),
      },
    ],
    [],
  );

  const filteredRows = useMemo(() => {
    const kw = search.trim().toLowerCase();
    return kw
      ? rows.filter((r) => r.external_id.toLowerCase().includes(kw))
      : rows;
  }, [rows, search]);

  return (
    <div className="space-y-4 p-6">
      <Title level={3} style={{ margin: 0 }}>
        工单
      </Title>

      <Card>
        <Space wrap style={{ marginBottom: 12 }}>
          <Segmented
            value={status}
            onChange={(v) => setStatus(v as TicketStatus | "")}
            options={STATUS_OPTIONS}
          />
          <Segmented
            value={severity}
            onChange={(v) => setSeverity(v as string)}
            options={SEVERITY_FILTER_OPTIONS}
          />
          <Input.Search
            placeholder="搜索工单号…"
            allowClear
            style={{ width: 200 }}
            onChange={(e) => setSearch(e.target.value)}
          />
        </Space>

        {loadError && (
          <Alert
            type="error"
            showIcon
            title={loadError}
            style={{ marginBottom: 12 }}
          />
        )}

        {loading ? (
          <Skeleton active paragraph={{ rows: 8 }} />
        ) : (
          <Table<Ticket>
            rowKey="external_id"
            size="small"
            columns={columns}
            dataSource={filteredRows}
            pagination={false}
            locale={{ emptyText: "暂无工单" }}
            scroll={{ x: "max-content" }}
          />
        )}

        {hasMore && !loading && rows.length > 0 && (
          <Flex justify="center" style={{ marginTop: 12 }}>
            <Button onClick={loadMore}>加载更多</Button>
          </Flex>
        )}
      </Card>
    </div>
  );
}
