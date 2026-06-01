import { ReloadOutlined } from "@ant-design/icons";
import {
  Alert,
  Button,
  Card,
  DatePicker,
  Flex,
  Input,
  Skeleton,
  Space,
  Table,
  Tooltip,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import type { Dayjs } from "dayjs";
import { format } from "date-fns";
import { useEffect, useMemo, useState } from "react";

import { listAudit, type AuditEntry } from "../../api/adminAudit";
import { useStaffSession } from "../../hooks/useStaffSession";

const { Title } = Typography;
const { RangePicker } = DatePicker;

function formatDateTime(val: string) {
  try {
    return format(new Date(val), "yyyy-MM-dd HH:mm:ss");
  } catch {
    return val;
  }
}

function DetailCell({ value }: { value: string | null }) {
  if (!value) return <span style={{ color: "rgba(0,0,0,0.45)" }}>—</span>;
  const truncated = value.length > 60 ? value.slice(0, 60) + "…" : value;
  if (value.length <= 60) {
    return (
      <span style={{ fontFamily: "ui-monospace, monospace", fontSize: 12 }}>
        {value}
      </span>
    );
  }
  return (
    <Tooltip title={<span style={{ wordBreak: "break-all" }}>{value}</span>} placement="topLeft">
      <span
        style={{
          fontFamily: "ui-monospace, monospace",
          fontSize: 12,
          color: "rgba(0,0,0,0.65)",
          cursor: "help",
        }}
      >
        {truncated}
      </span>
    </Tooltip>
  );
}

interface FilterState {
  actor: string;
  action: string;
  dateRange: [Dayjs | null, Dayjs | null] | null;
}

export function AuditCenterRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "engineer" || role === "admin";

  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [filter, setFilter] = useState<FilterState>({
    actor: "",
    action: "",
    dateRange: null,
  });

  function reload(f: FilterState = filter) {
    if (!token) return;
    setLoading(true);
    setErr("");
    listAudit(token, {
      actor: f.actor || undefined,
      action: f.action || undefined,
    })
      .then((rows) => {
        // Client-side date filter (API doesn't support date range params)
        const from = f.dateRange?.[0]?.startOf("day").valueOf() ?? null;
        const to = f.dateRange?.[1]?.endOf("day").valueOf() ?? null;
        const filtered =
          from != null || to != null
            ? rows.filter((r) => {
                const t = new Date(r.created_at).getTime();
                if (from != null && t < from) return false;
                if (to != null && t > to) return false;
                return true;
              })
            : rows;
        setEntries(filtered);
      })
      .catch(() => setErr("加载失败，请重试"))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token) return;
    if (!allowed) {
      setErr("需要工程或管理员权限");
      setLoading(false);
      return;
    }
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role]);

  const columns: ColumnsType<AuditEntry> = useMemo(
    () => [
      {
        title: "时间",
        dataIndex: "created_at",
        width: 180,
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
        title: "操作人",
        dataIndex: "actor",
        width: 160,
        sorter: (a, b) => a.actor.localeCompare(b.actor),
        render: (v: string) => (
          <span style={{ fontFamily: "ui-monospace, monospace", fontSize: 12 }}>
            {v}
          </span>
        ),
      },
      {
        title: "动作",
        dataIndex: "action",
        width: 180,
        sorter: (a, b) => a.action.localeCompare(b.action),
        render: (v: string) => (
          <span style={{ fontFamily: "ui-monospace, monospace", fontSize: 12 }}>
            {v}
          </span>
        ),
      },
      {
        title: "对象",
        key: "target",
        width: 200,
        render: (_: unknown, row: AuditEntry) => {
          if (!row.target_type) return <span style={{ color: "rgba(0,0,0,0.45)" }}>—</span>;
          return (
            <span style={{ fontFamily: "ui-monospace, monospace", fontSize: 12 }}>
              {row.target_type}
              {row.target_id ? `:${row.target_id}` : ""}
            </span>
          );
        },
      },
      {
        title: "详情",
        dataIndex: "detail_json",
        render: (v: string | null) => <DetailCell value={v} />,
      },
    ],
    [],
  );

  return (
    <div className="space-y-4 p-6">
      <Flex justify="space-between" align="flex-start" wrap="wrap" gap="middle">
        <Title level={3} style={{ margin: 0 }}>
          操作审计
        </Title>
        <Button
          icon={<ReloadOutlined spin={loading} />}
          onClick={() => reload()}
          disabled={loading}
        >
          刷新
        </Button>
      </Flex>

      {err && <Alert type="error" showIcon title={err} />}

      {allowed && (
        <Card>
          <Space wrap style={{ marginBottom: 12 }}>
            <Input
              placeholder="搜索操作人…"
              value={filter.actor}
              onChange={(e) => setFilter((f) => ({ ...f, actor: e.target.value }))}
              style={{ width: 200 }}
              allowClear
            />
            <Input
              placeholder="搜索动作…"
              value={filter.action}
              onChange={(e) => setFilter((f) => ({ ...f, action: e.target.value }))}
              style={{ width: 200 }}
              allowClear
            />
            <RangePicker
              value={filter.dateRange}
              onChange={(v) =>
                setFilter((f) => ({
                  ...f,
                  dateRange: v as [Dayjs | null, Dayjs | null] | null,
                }))
              }
            />
            <Button type="primary" onClick={() => reload(filter)} disabled={loading}>
              筛选
            </Button>
            {filter.dateRange && (
              <Button
                type="text"
                onClick={() => {
                  const next = { ...filter, dateRange: null };
                  setFilter(next);
                  reload(next);
                }}
              >
                清除日期
              </Button>
            )}
          </Space>

          {loading ? (
            <Skeleton active paragraph={{ rows: 8 }} />
          ) : (
            <Table<AuditEntry>
              rowKey={(r) => `${r.created_at}-${r.actor}-${r.action}`}
              size="small"
              columns={columns}
              dataSource={entries}
              pagination={{ pageSize: 20, showSizeChanger: true }}
              locale={{ emptyText: "暂无审计记录" }}
              scroll={{ x: "max-content" }}
            />
          )}
        </Card>
      )}
    </div>
  );
}
