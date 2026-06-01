import { ReloadOutlined } from "@ant-design/icons";
import {
  Alert,
  Button,
  Card,
  Flex,
  Input,
  Select,
  Skeleton,
  Table,
  Tag,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useCallback, useEffect, useMemo, useState } from "react";

import { listPresence, type Presence } from "../../api/staffPresence";
import { useStaffSession } from "../../hooks/useStaffSession";

const { Title } = Typography;

function formatLastSeen(raw: string): string {
  try {
    return new Date(raw).toLocaleString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return raw;
  }
}

const STATUS_LABEL: Record<string, string> = {
  online: "在线",
  away: "离开",
};

export function PresenceRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "supervisor" || role === "admin";

  const [rows, setRows] = useState<Presence[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const reload = useCallback(() => {
    if (!token) return;
    setLoading(true);
    setLoadError("");
    listPresence(token)
      .then((d) => setRows(d.all))
      .catch((e: unknown) =>
        setLoadError(e instanceof Error ? e.message : "加载失败"),
      )
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => {
    if (!token) return;
    if (!allowed) {
      setLoadError("需要主管或管理员权限");
      setLoading(false);
      return;
    }
    reload();
  }, [token, role]); // eslint-disable-line react-hooks/exhaustive-deps

  const columns: ColumnsType<Presence> = useMemo(
    () => [
      {
        title: "Staff ID",
        dataIndex: "staff_id",
        sorter: (a, b) => a.staff_id.localeCompare(b.staff_id),
      },
      {
        title: "状态",
        dataIndex: "status",
        width: 120,
        render: (s: string) => (
          <Tag color={s === "online" ? "green" : "default"}>
            {STATUS_LABEL[s] ?? s}
          </Tag>
        ),
      },
      {
        title: "上次活跃",
        dataIndex: "last_seen_at",
        sorter: (a, b) =>
          new Date(a.last_seen_at).getTime() -
          new Date(b.last_seen_at).getTime(),
        render: (v: string) => formatLastSeen(v),
      },
    ],
    [],
  );

  const filteredRows = useMemo(() => {
    const kw = search.trim().toLowerCase();
    return rows.filter((r) => {
      if (kw && !r.staff_id.toLowerCase().includes(kw)) return false;
      if (statusFilter !== "all" && r.status !== statusFilter) return false;
      return true;
    });
  }, [rows, search, statusFilter]);

  return (
    <div className="space-y-4 p-6">
      <Flex justify="space-between" align="flex-start" wrap="wrap" gap="middle">
        <Title level={3} style={{ margin: 0 }}>
          在线状态
        </Title>
        {allowed && (
          <Button
            icon={<ReloadOutlined />}
            onClick={reload}
            disabled={loading}
          >
            刷新
          </Button>
        )}
      </Flex>

      {loadError && <Alert type="error" showIcon title={loadError} />}

      {loading ? (
        <Card>
          <Skeleton active paragraph={{ rows: 5 }} />
        </Card>
      ) : (
        <Card>
          <Flex gap="small" style={{ marginBottom: 12 }}>
            <Input.Search
              placeholder="按 staff_id 搜索…"
              allowClear
              style={{ width: 240 }}
              onChange={(e) => setSearch(e.target.value)}
            />
            <Select
              value={statusFilter}
              onChange={setStatusFilter}
              style={{ width: 140 }}
              options={[
                { value: "all", label: "全部状态" },
                { value: "online", label: "在线" },
                { value: "away", label: "离开" },
              ]}
            />
          </Flex>
          <Table<Presence>
            rowKey="staff_id"
            size="middle"
            columns={columns}
            dataSource={filteredRows}
            pagination={{ pageSize: 20, showSizeChanger: true }}
            locale={{ emptyText: "暂无客服在线记录" }}
            scroll={{ x: "max-content" }}
          />
        </Card>
      )}
    </div>
  );
}
