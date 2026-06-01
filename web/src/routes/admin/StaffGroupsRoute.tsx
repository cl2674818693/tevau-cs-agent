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
  Skeleton,
  Table,
  Tag,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { format } from "date-fns";
import { useEffect, useMemo, useState } from "react";

import {
  createGroup,
  deleteGroup,
  listGroups,
  patchGroup,
  type StaffGroup,
} from "../../api/adminStaffGroups";
import { useStaffSession } from "../../hooks/useStaffSession";

const { Title } = Typography;
const { TextArea } = Input;

function GroupDrawer({
  open,
  onOpenChange,
  editing,
  token,
  onSuccess,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  editing: StaffGroup | null;
  token: string;
  onSuccess: () => void;
}) {
  const [form] = Form.useForm<{ name: string; description?: string }>();
  const { message } = App.useApp();

  useEffect(() => {
    if (open) {
      form.setFieldsValue({
        name: editing?.name ?? "",
        description: editing?.description ?? "",
      });
    }
  }, [open, editing, form]);

  async function onSubmit(values: { name: string; description?: string }) {
    try {
      if (editing) {
        await patchGroup(token, editing.id, {
          name: values.name,
          description: values.description || undefined,
        });
      } else {
        await createGroup(token, {
          name: values.name,
          description: values.description || undefined,
        });
      }
      message.success("已保存");
      onOpenChange(false);
      onSuccess();
    } catch (err) {
      message.error(err instanceof Error ? err.message : "保存失败");
    }
  }

  return (
    <Drawer
      title={editing ? "编辑分组" : "新建分组"}
      open={open}
      onClose={() => onOpenChange(false)}
      size="default"
    >
      <Form form={form} layout="vertical" onFinish={onSubmit}>
        <Form.Item
          name="name"
          label="名称"
          rules={[{ required: true, message: "名称必填" }]}
        >
          <Input placeholder="分组名称" />
        </Form.Item>
        <Form.Item name="description" label="描述（可选）">
          <TextArea rows={3} placeholder="分组描述" />
        </Form.Item>
        <Form.Item style={{ marginBottom: 0 }}>
          <Flex justify="flex-end" gap="small">
            <Button onClick={() => onOpenChange(false)}>取消</Button>
            <Button type="primary" htmlType="submit">
              保存
            </Button>
          </Flex>
        </Form.Item>
      </Form>
    </Drawer>
  );
}

export function StaffGroupsRoute() {
  const { token } = useStaffSession();
  const { message, modal } = App.useApp();
  const [groups, setGroups] = useState<StaffGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<StaffGroup | null>(null);
  const [search, setSearch] = useState("");

  function reload() {
    if (!token) return;
    setLoading(true);
    listGroups(token)
      .then(setGroups)
      .catch((e: unknown) =>
        setLoadError(e instanceof Error ? e.message : "加载失败"),
      )
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  function openCreate() {
    setEditing(null);
    setDrawerOpen(true);
  }

  function openEdit(g: StaffGroup) {
    setEditing(g);
    setDrawerOpen(true);
  }

  async function handleToggle(g: StaffGroup) {
    if (!token) return;
    try {
      await patchGroup(token, g.id, { active: g.active ? 0 : 1 });
      reload();
    } catch (err) {
      message.error(err instanceof Error ? err.message : "操作失败");
    }
  }

  function handleDelete(g: StaffGroup) {
    modal.confirm({
      title: `确认删除分组"${g.name}"？`,
      content: "此操作不可撤销。",
      okText: "删除",
      okType: "danger",
      cancelText: "取消",
      onOk: async () => {
        if (!token) return;
        try {
          await deleteGroup(token, g.id);
          message.success("已删除");
          reload();
        } catch (err) {
          message.error(err instanceof Error ? err.message : "删除失败");
        }
      },
    });
  }

  const columns: ColumnsType<StaffGroup> = useMemo(
    () => [
      {
        title: "名称",
        dataIndex: "name",
        sorter: (a, b) => a.name.localeCompare(b.name),
      },
      {
        title: "描述",
        dataIndex: "description",
        render: (v: string | null) => v ?? "-",
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
        render: (_: unknown, g: StaffGroup) => (
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

  const filteredGroups = useMemo(() => {
    const kw = search.trim().toLowerCase();
    return kw ? groups.filter((g) => g.name.toLowerCase().includes(kw)) : groups;
  }, [groups, search]);

  return (
    <div className="space-y-4 p-6">
      <Flex justify="space-between" align="flex-start" wrap="wrap" gap="middle">
        <Title level={3} style={{ margin: 0 }}>
          客服分组
        </Title>
        <Button type="primary" onClick={openCreate}>
          新建分组
        </Button>
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
              placeholder="搜索分组名…"
              allowClear
              style={{ width: 240 }}
              onChange={(e) => setSearch(e.target.value)}
            />
          </Flex>
          <Table<StaffGroup>
            rowKey="id"
            size="middle"
            columns={columns}
            dataSource={filteredGroups}
            pagination={{ pageSize: 20, showSizeChanger: true }}
            locale={{ emptyText: "暂无分组" }}
          />
        </Card>
      )}

      {token && (
        <GroupDrawer
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
