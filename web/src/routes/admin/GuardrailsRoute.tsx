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
  createGuardrail,
  deleteGuardrail,
  type Guardrail,
  listGuardrails,
  patchGuardrail,
  setGuardrailActive,
} from "../../api/adminGuardrails";
import { useStaffSession } from "../../hooks/useStaffSession";

const { Title } = Typography;

const GUARDRAIL_TYPES = ["blocklist", "sensitive_word", "scope_toggle"] as const;
const GUARDRAIL_ACTIONS = ["block", "flag"] as const;

type FormValues = {
  type: (typeof GUARDRAIL_TYPES)[number];
  pattern: string;
  action: (typeof GUARDRAIL_ACTIONS)[number];
};

/** 创建 + 编辑共用一个 Drawer：editing=null 即新建 */
function GuardrailDrawer({
  open,
  onOpenChange,
  editing,
  token,
  onSuccess,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  editing: Guardrail | null;
  token: string;
  onSuccess: () => void;
}) {
  const [form] = Form.useForm<FormValues>();
  const { message } = App.useApp();

  useEffect(() => {
    if (open) {
      form.setFieldsValue(
        editing
          ? {
              type: editing.type as FormValues["type"],
              pattern: editing.pattern,
              action: editing.action as FormValues["action"],
            }
          : { type: "sensitive_word", pattern: "", action: "block" },
      );
    }
  }, [open, editing, form]);

  async function onSubmit(values: FormValues) {
    try {
      if (editing) {
        await patchGuardrail(token, editing.id, values);
        message.success("规则已更新");
      } else {
        await createGuardrail(token, values);
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
      title={editing ? `编辑规则 #${editing.id}` : "新建拦截规则"}
      open={open}
      onClose={() => onOpenChange(false)}
      size="default"
    >
      <Form form={form} layout="vertical" onFinish={onSubmit}>
        <Form.Item name="type" label="类型" rules={[{ required: true }]}>
          <Select
            options={GUARDRAIL_TYPES.map((t) => ({ value: t, label: t }))}
          />
        </Form.Item>
        <Form.Item
          name="pattern"
          label="pattern"
          rules={[{ required: true, message: "pattern 必填" }]}
        >
          <Input placeholder="subject_id / 词 / scope 名" />
        </Form.Item>
        <Form.Item name="action" label="动作" rules={[{ required: true }]}>
          <Select
            options={GUARDRAIL_ACTIONS.map((a) => ({ value: a, label: a }))}
          />
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

export function GuardrailsRoute() {
  const { token, role } = useStaffSession();
  const { message, modal } = App.useApp();
  const allowed = role === "engineer" || role === "admin";

  const [rules, setRules] = useState<Guardrail[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<Guardrail | null>(null);
  const [search, setSearch] = useState("");

  function reload() {
    if (!token) return;
    setLoading(true);
    listGuardrails(token)
      .then(setRules)
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

  function openCreate() {
    setEditing(null);
    setDrawerOpen(true);
  }

  function openEdit(g: Guardrail) {
    setEditing(g);
    setDrawerOpen(true);
  }

  async function handleToggle(g: Guardrail) {
    if (!token) return;
    try {
      await setGuardrailActive(token, g.id, g.active ? 0 : 1);
      message.success(g.active ? "已停用" : "已启用");
      reload();
    } catch (err) {
      message.error(err instanceof Error ? err.message : "操作失败");
    }
  }

  function handleDelete(g: Guardrail) {
    modal.confirm({
      title: `确认删除规则？`,
      content: `${g.type} = ${g.pattern}（此操作不可撤销）`,
      okText: "删除",
      okType: "danger",
      cancelText: "取消",
      onOk: async () => {
        if (!token) return;
        try {
          await deleteGuardrail(token, g.id);
          message.success("已删除");
          reload();
        } catch (err) {
          message.error(err instanceof Error ? err.message : "删除失败");
        }
      },
    });
  }

  const columns: ColumnsType<Guardrail> = useMemo(
    () => [
      {
        title: "ID",
        dataIndex: "id",
        width: 80,
        sorter: (a, b) => a.id - b.id,
      },
      { title: "类型", dataIndex: "type", width: 140 },
      { title: "pattern", dataIndex: "pattern" },
      { title: "动作", dataIndex: "action", width: 100 },
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
        render: (_: unknown, g: Guardrail) => (
          <Dropdown
            menu={{
              items: [
                { key: "edit", label: "编辑", onClick: () => openEdit(g) },
                {
                  key: "toggle",
                  label: g.active ? "停用" : "启用",
                  onClick: () => handleToggle(g),
                },
                { type: "divider" },
                {
                  key: "delete",
                  label: "删除",
                  danger: true,
                  onClick: () => handleDelete(g),
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
    [token],
  );

  const filteredRules = useMemo(() => {
    const kw = search.trim().toLowerCase();
    return kw
      ? rules.filter((r) => r.pattern.toLowerCase().includes(kw))
      : rules;
  }, [rules, search]);

  return (
    <div className="space-y-4 p-6">
      <Flex justify="space-between" align="flex-start" wrap="wrap" gap="middle">
        <Title level={3} style={{ margin: 0 }}>
          范围拦截
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
              placeholder="搜索 pattern…"
              allowClear
              style={{ width: 240 }}
              onChange={(e) => setSearch(e.target.value)}
            />
          </Flex>
          <Table<Guardrail>
            rowKey="id"
            size="middle"
            columns={columns}
            dataSource={filteredRules}
            pagination={{ pageSize: 20, showSizeChanger: true }}
            locale={{ emptyText: "暂无拦截规则" }}
          />
        </Card>
      )}

      {token && allowed && (
        <GuardrailDrawer
          open={drawerOpen}
          onOpenChange={setDrawerOpen}
          editing={editing}
          token={token}
          onSuccess={reload}
        />
      )}
    </div>
  );
}
