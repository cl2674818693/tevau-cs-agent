import { App, Button, Card, Checkbox, Flex, Skeleton, Table, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { getMatrix, type RbacMatrix, upsertMatrix } from "../../api/adminRbac";
import { useStaffSession } from "../../hooks/useStaffSession";

const { Title, Text } = Typography;

// ── 中文 label：让运营一眼看懂；原英文 key 保留作副标题（审计/排查用） ──────────
// 文案与左侧导航栏 nav-config.ts 严格对齐，避免认知割裂。
const PERM_LABELS: Record<string, string> = {
  "admin.dashboard": "数据大盘",
  "admin.staff": "客服账号",
  "admin.performance": "客服绩效",
  "admin.qa": "会话质检",
  "admin.sla": "SLA 策略",
  "admin.tools": "工具策略",
  "admin.cost": "成本大盘",
  "admin.audit": "操作审计",
  "admin.prompts": "Prompt 灰度",
  "admin.rbac": "角色权限",
  "admin.staff_groups": "客服分组",
  "admin.presence": "在线状态",
  "admin.shifts": "排班",
  "admin.routing": "会话路由",
  "admin.prompt_editor": "Prompt 编辑",
  "admin.knowledge": "知识库",
  "admin.guardrails": "范围拦截",
};

const ROLE_LABELS: Record<string, string> = {
  agent: "客服",
  senior: "高级客服",
  supervisor: "主管",
  engineer: "工程师",
  manager: "经理",
  admin: "管理员",
};

type LocalMatrix = Record<string, Record<string, boolean>>;
type PermRow = { permKey: string };

function buildColumns(
  roles: string[],
  matrix: LocalMatrix,
  onToggle: (role: string, perm: string, v: boolean) => void,
): ColumnsType<PermRow> {
  return [
    {
      title: "模块",
      dataIndex: "permKey",
      fixed: "left",
      width: 200,
      render: (p: string) => (
        <div>
          <div className="font-medium">{PERM_LABELS[p] ?? p}</div>
          <div className="mt-0.5 font-mono text-[11px] text-gray-400">{p}</div>
        </div>
      ),
    },
    ...roles.map<ColumnsType<PermRow>[number]>((r) => ({
      title: (
        <div className="text-center">
          <div className="font-medium">{ROLE_LABELS[r] ?? r}</div>
          <div className="mt-0.5 font-mono text-[11px] font-normal text-gray-400">
            {r}
          </div>
        </div>
      ),
      key: r,
      align: "center" as const,
      width: 100,
      render: (_: unknown, row: PermRow) => (
        <Checkbox
          aria-label={`${PERM_LABELS[row.permKey] ?? row.permKey}/${ROLE_LABELS[r] ?? r}`}
          checked={matrix[r]?.[row.permKey] ?? false}
          onChange={(e) => onToggle(r, row.permKey, e.target.checked)}
        />
      ),
    })),
  ];
}

export function RbacRoute() {
  const { token, role } = useStaffSession();
  const { message } = App.useApp();
  const allowed = role === "admin";

  const [data, setData] = useState<RbacMatrix | null>(null);
  const [local, setLocal] = useState<LocalMatrix>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!token || !allowed) {
      setLoading(false);
      return;
    }
    setLoading(true);
    getMatrix(token)
      .then((d) => {
        setData(d);
        setLocal(d.matrix);
      })
      .catch(() => message.error("加载失败"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role]);

  function toggle(r: string, p: string, v: boolean) {
    setLocal((prev) => ({ ...prev, [r]: { ...prev[r], [p]: v } }));
  }

  const upsertItems = useMemo(() => {
    if (!data) return [];
    return data.roles.flatMap((r) =>
      data.permission_keys.map((p) => ({
        role: r,
        permission_key: p,
        allowed: local[r]?.[p] ? 1 : 0,
      })),
    );
  }, [data, local]);

  function reset() {
    if (data) setLocal(data.matrix);
  }

  async function save() {
    if (!token) return;
    setSaving(true);
    try {
      await upsertMatrix(token, upsertItems);
      message.success("权限已保存");
    } catch (e) {
      message.error(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  const columns = useMemo(
    () =>
      data ? buildColumns(data.roles, local, toggle) : [],
    [data, local],
  );
  const rows: PermRow[] = useMemo(
    () => (data ? data.permission_keys.map((p) => ({ permKey: p })) : []),
    [data],
  );

  return (
    <div className="space-y-4 p-6">
      <Flex justify="space-between" align="flex-start" wrap="wrap" gap="middle">
        <Title level={3} style={{ margin: 0 }}>
          角色权限
        </Title>
        {allowed && data && (
          <Flex gap="small">
            <Button onClick={reset} disabled={saving}>
              重置
            </Button>
            <Button type="primary" onClick={save} loading={saving}>
              保存
            </Button>
          </Flex>
        )}
      </Flex>

      <Text type="secondary">
        改完保存后，rbac.is_permitted 即时按新矩阵生效（缓存失效）。改角色仍走
        <Link to="/admin/staff" style={{ marginLeft: 4 }}>
          客服账号
        </Link>
        。
      </Text>

      {loading ? (
        <Card>
          <Skeleton active paragraph={{ rows: 8 }} />
        </Card>
      ) : allowed && data ? (
        <Card>
          <Table<PermRow>
            rowKey="permKey"
            size="middle"
            columns={columns}
            dataSource={rows}
            pagination={false}
            scroll={{ x: "max-content" }}
          />
        </Card>
      ) : (
        <Card>
          <Text type="secondary">需要管理员权限。</Text>
        </Card>
      )}
    </div>
  );
}
