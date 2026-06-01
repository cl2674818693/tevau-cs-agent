import {
  Alert,
  App,
  Button,
  Card,
  Flex,
  Input,
  Skeleton,
  Switch,
  Table,
  Tag,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useMemo, useState } from "react";

import {
  listToolPolicies,
  POLICY_ROLES,
  type ToolPolicy,
  TOOL_NAMES,
  upsertToolPolicies,
} from "../../api/adminToolPolicies";
import { useStaffSession } from "../../hooks/useStaffSession";

const { Title, Text } = Typography;

type FlatRow = {
  tool_name: string;
  role: string;
  allowed: number;
  unmask_allowed: number;
};

function emptyRows(): FlatRow[] {
  const out: FlatRow[] = [];
  for (const t of TOOL_NAMES)
    for (const r of POLICY_ROLES)
      out.push({ tool_name: t, role: r, allowed: 0, unmask_allowed: 0 });
  return out;
}

function applyApiRows(rows: ToolPolicy[]): FlatRow[] {
  const base = emptyRows();
  for (const row of rows) {
    const found = base.find(
      (r) => r.tool_name === row.tool_name && r.role === row.role,
    );
    if (found) {
      found.allowed = Number(row.allowed);
      found.unmask_allowed = Number(row.unmask_allowed);
    }
  }
  return base;
}

export function ToolPoliciesRoute() {
  const { token, role } = useStaffSession();
  const { message } = App.useApp();
  const allowed = role === "engineer" || role === "admin";

  const [rows, setRows] = useState<FlatRow[]>(emptyRows);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState("");

  function reload() {
    if (!token) return;
    setLoading(true);
    listToolPolicies(token)
      .then((data) => setRows(applyApiRows(data)))
      .catch((e: unknown) =>
        setLoadError(e instanceof Error ? e.message : "加载失败"),
      )
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token || !allowed) {
      setLoadError("需要工程或管理员权限");
      setLoading(false);
      return;
    }
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role]);

  async function save() {
    if (!token) return;
    setSaving(true);
    try {
      await upsertToolPolicies(token, rows);
      message.success("已保存（缓存已刷新）");
    } catch (e) {
      message.error(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  function toggle(row: FlatRow, field: "allowed" | "unmask_allowed") {
    setRows((prev) =>
      prev.map((r) =>
        r.tool_name === row.tool_name && r.role === row.role
          ? { ...r, [field]: r[field] === 1 ? 0 : 1 }
          : r,
      ),
    );
  }

  const columns: ColumnsType<FlatRow> = useMemo(
    () => [
      {
        title: "工具",
        dataIndex: "tool_name",
        sorter: (a, b) => a.tool_name.localeCompare(b.tool_name),
        render: (v: string) => (
          <span style={{ fontFamily: "ui-monospace, monospace", fontSize: 12 }}>
            {v}
          </span>
        ),
      },
      {
        title: "角色",
        dataIndex: "role",
        width: 140,
        render: (v: string) => <Tag>{v}</Tag>,
      },
      {
        title: "允许调用",
        dataIndex: "allowed",
        width: 120,
        align: "center",
        render: (_: unknown, row: FlatRow) => (
          <Switch
            checked={row.allowed === 1}
            onChange={() => toggle(row, "allowed")}
            disabled={!allowed}
          />
        ),
      },
      {
        title: "允许解锁",
        dataIndex: "unmask_allowed",
        width: 120,
        align: "center",
        render: (_: unknown, row: FlatRow) => (
          <Switch
            checked={row.unmask_allowed === 1}
            onChange={() => toggle(row, "unmask_allowed")}
            disabled={!allowed}
          />
        ),
      },
    ],
    [allowed],
  );

  const filteredRows = useMemo(() => {
    const kw = search.trim().toLowerCase();
    return kw ? rows.filter((r) => r.tool_name.toLowerCase().includes(kw)) : rows;
  }, [rows, search]);

  return (
    <div className="space-y-4 p-6">
      <Flex justify="space-between" align="flex-start" wrap="wrap" gap="middle">
        <Title level={3} style={{ margin: 0 }}>
          工具策略
        </Title>
        {allowed && (
          <Button type="primary" onClick={save} loading={saving} disabled={loading}>
            保存
          </Button>
        )}
      </Flex>

      {loadError && <Alert type="error" showIcon title={loadError} />}

      {loading ? (
        <Card>
          <Skeleton active paragraph={{ rows: 8 }} />
        </Card>
      ) : (
        <Card>
          <Flex style={{ marginBottom: 12 }}>
            <Input.Search
              placeholder="搜索工具名…"
              allowClear
              style={{ width: 260 }}
              onChange={(e) => setSearch(e.target.value)}
            />
          </Flex>
          <Table<FlatRow>
            rowKey={(r) => `${r.tool_name}-${r.role}`}
            size="small"
            columns={columns}
            dataSource={filteredRows}
            pagination={{ pageSize: 50, showSizeChanger: true }}
            locale={{ emptyText: "无匹配条目" }}
            scroll={{ x: "max-content" }}
          />
        </Card>
      )}

      <Text type="secondary" style={{ fontSize: 12 }}>
        admin 角色默认全部允许，不在矩阵中显示。空表回退到 M1 默认白名单。
      </Text>
    </div>
  );
}
