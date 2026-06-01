import { MoreOutlined } from "@ant-design/icons";
import {
  Alert,
  App,
  Button,
  Card,
  Drawer,
  Dropdown,
  Flex,
  Form,
  Input,
  InputNumber,
  Select,
  Skeleton,
  Table,
  Tag,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { format } from "date-fns";
import { useEffect, useMemo, useState } from "react";

import {
  createRule,
  deleteRule,
  listRules,
  patchRule,
  type RoutingRule,
  setRuleActive,
} from "../../api/adminRoutingRules";
import { listGroups, type StaffGroup } from "../../api/adminStaffGroups";
import { useStaffSession } from "../../hooks/useStaffSession";

const { Title } = Typography;

const MATCH_TYPES = ["user_type", "scope", "keyword"] as const;

type FormValues = {
  match_type: (typeof MATCH_TYPES)[number];
  match_value: string;
  target_group_id: number;
  priority: number;
};

/** 创建 + 编辑共用一个 Drawer：editing=null 即新建 */
function RuleDrawer({
  open,
  onOpenChange,
  editing,
  token,
  groups,
  onSuccess,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  editing: RoutingRule | null;
  token: string;
  groups: StaffGroup[];
  onSuccess: () => void;
}) {
  const [form] = Form.useForm<FormValues>();
  const { message } = App.useApp();

  useEffect(() => {
    if (open) {
      form.setFieldsValue(
        editing
          ? {
              match_type: editing.match_type as FormValues["match_type"],
              match_value: editing.match_value,
              target_group_id: editing.target_group_id,
              priority: editing.priority,
            }
          : {
              match_type: "user_type",
              match_value: "",
              target_group_id: groups[0]?.id ?? 0,
              priority: 100,
            },
      );
    }
  }, [open, editing, groups, form]);

  async function onSubmit(values: FormValues) {
    try {
      if (editing) {
        await patchRule(token, editing.id, values);
        message.success("规则已更新");
      } else {
        await createRule(token, values);
        message.success("规则已创建");
      }
      onOpenChange(false);
      onSuccess();
    } catch (err) {
      message.error(err instanceof Error ? err.message : "保存失败");
    }
  }

  return (
    <Drawer
      title={editing ? `编辑规则 #${editing.id}` : "新建会话路由规则"}
      open={open}
      onClose={() => onOpenChange(false)}
      size="default"
    >
      <Form form={form} layout="vertical" onFinish={onSubmit}>
        <Form.Item
          name="match_type"
          label="匹配类型"
          rules={[{ required: true }]}
        >
          <Select options={MATCH_TYPES.map((t) => ({ value: t, label: t }))} />
        </Form.Item>
        <Form.Item
          name="match_value"
          label="匹配值"
          rules={[{ required: true, message: "匹配值必填" }]}
        >
          <Input placeholder="c / b / 关键词 / scope 名" />
        </Form.Item>
        <Form.Item
          name="target_group_id"
          label="目标分组"
          rules={[
            { required: true, type: "number", min: 1, message: "目标分组必填" },
          ]}
        >
          <Select
            placeholder="选择目标分组"
            options={groups.map((g) => ({ value: g.id, label: g.name }))}
          />
        </Form.Item>
        <Form.Item
          name="priority"
          label="优先级（数字越小越优先）"
          rules={[{ required: true, type: "number", min: 0 }]}
        >
          <InputNumber min={0} style={{ width: "100%" }} />
        </Form.Item>
        <Form.Item style={{ marginBottom: 0 }}>
          <Flex justify="flex-end" gap="small">
            <Button onClick={() => onOpenChange(false)}>取消</Button>
            <Button type="primary" htmlType="submit">
              {editing ? "保存" : "创建"}
            </Button>
          </Flex>
        </Form.Item>
      </Form>
    </Drawer>
  );
}

export function RoutingRulesRoute() {
  const { token, role } = useStaffSession();
  const { message, modal } = App.useApp();
  const allowed = role === "supervisor" || role === "admin";

  const [rules, setRules] = useState<RoutingRule[]>([]);
  const [groups, setGroups] = useState<StaffGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<RoutingRule | null>(null);
  const [search, setSearch] = useState("");

  function reload() {
    if (!token) return;
    setLoading(true);
    Promise.all([listRules(token), listGroups(token)])
      .then(([rs, gs]) => {
        setRules(rs);
        setGroups(gs);
      })
      .catch((e: unknown) =>
        setLoadError(e instanceof Error ? e.message : "加载失败"),
      )
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token || !allowed) {
      setLoadError("需要主管或管理员权限");
      setLoading(false);
      return;
    }
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role]);

  const groupName = (id: number) =>
    groups.find((g) => g.id === id)?.name ?? `#${id}`;

  function openCreate() {
    setEditing(null);
    setDrawerOpen(true);
  }

  function openEdit(r: RoutingRule) {
    setEditing(r);
    setDrawerOpen(true);
  }

  async function handleToggle(r: RoutingRule) {
    if (!token) return;
    try {
      await setRuleActive(token, r.id, r.active ? 0 : 1);
      message.success(r.active ? "已停用" : "已启用");
      reload();
    } catch (err) {
      message.error(err instanceof Error ? err.message : "操作失败");
    }
  }

  function handleDelete(r: RoutingRule) {
    modal.confirm({
      title: `确认删除规则？`,
      content: `${r.match_type} = ${r.match_value}（此操作不可撤销）`,
      okText: "删除",
      okType: "danger",
      cancelText: "取消",
      onOk: async () => {
        if (!token) return;
        try {
          await deleteRule(token, r.id);
          message.success("已删除");
          reload();
        } catch (err) {
          message.error(err instanceof Error ? err.message : "删除失败");
        }
      },
    });
  }

  const columns: ColumnsType<RoutingRule> = useMemo(
    () => [
      {
        title: "优先级",
        dataIndex: "priority",
        width: 100,
        sorter: (a, b) => a.priority - b.priority,
      },
      { title: "类型", dataIndex: "match_type", width: 140 },
      { title: "匹配值", dataIndex: "match_value" },
      {
        title: "目标分组",
        key: "target_group",
        render: (_: unknown, r: RoutingRule) => groupName(r.target_group_id),
      },
      {
        title: "状态",
        dataIndex: "active",
        width: 100,
        render: (v: number) =>
          v ? <Tag color="green">启用</Tag> : <Tag>停用</Tag>,
      },
      {
        title: "创建时间",
        dataIndex: "created_at",
        width: 160,
        render: (v: string) => {
          try {
            return format(new Date(v), "yyyy-MM-dd HH:mm");
          } catch {
            return v;
          }
        },
      },
      {
        title: "",
        key: "actions",
        width: 60,
        align: "right",
        render: (_: unknown, r: RoutingRule) => (
          <Dropdown
            menu={{
              items: [
                { key: "edit", label: "编辑", onClick: () => openEdit(r) },
                {
                  key: "toggle",
                  label: r.active ? "停用" : "启用",
                  onClick: () => handleToggle(r),
                },
                { type: "divider" },
                {
                  key: "delete",
                  label: "删除",
                  danger: true,
                  onClick: () => handleDelete(r),
                },
              ],
            }}
            trigger={["click"]}
          >
            <Button type="text" icon={<MoreOutlined />} size="small" />
          </Dropdown>
        ),
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [token, groups],
  );

  const filteredRules = useMemo(() => {
    const kw = search.trim().toLowerCase();
    return kw
      ? rules.filter((r) => r.match_value.toLowerCase().includes(kw))
      : rules;
  }, [rules, search]);

  return (
    <div className="space-y-4 p-6">
      <Flex justify="space-between" align="flex-start" wrap="wrap" gap="middle">
        <Title level={3} style={{ margin: 0 }}>
          会话路由
        </Title>
        {allowed && (
          <Button type="primary" onClick={openCreate}>
            新建规则
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
          <Flex style={{ marginBottom: 12 }}>
            <Input.Search
              placeholder="搜索匹配值…"
              allowClear
              style={{ width: 240 }}
              onChange={(e) => setSearch(e.target.value)}
            />
          </Flex>
          <Table<RoutingRule>
            rowKey="id"
            size="middle"
            columns={columns}
            dataSource={filteredRules}
            pagination={{ pageSize: 20, showSizeChanger: true }}
            locale={{ emptyText: "暂无路由规则" }}
          />
        </Card>
      )}

      {token && allowed && (
        <RuleDrawer
          open={drawerOpen}
          onOpenChange={setDrawerOpen}
          editing={editing}
          token={token}
          groups={groups}
          onSuccess={reload}
        />
      )}
    </div>
  );
}
