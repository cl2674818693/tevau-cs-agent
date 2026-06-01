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
  createKnowledge,
  deleteKnowledge,
  type KnowledgeEntry,
  listKnowledge,
  publishKnowledge,
} from "../../api/adminKnowledge";
import { useStaffSession } from "../../hooks/useStaffSession";

const { Title } = Typography;
const { TextArea } = Input;

const TYPES = ["faq", "api_doc", "error_code"] as const;

function KnowledgeDrawer({
  open,
  onOpenChange,
  token,
  onSuccess,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  token: string;
  onSuccess: () => void;
}) {
  const [form] = Form.useForm<{
    type: string;
    key: string;
    title: string;
    content?: string;
    locale?: string;
  }>();
  const { message } = App.useApp();

  useEffect(() => {
    if (open) {
      form.setFieldsValue({
        type: "faq",
        key: "",
        title: "",
        content: "",
        locale: "",
      });
    }
  }, [open, form]);

  async function onSubmit(values: {
    type: string;
    key: string;
    title: string;
    content?: string;
    locale?: string;
  }) {
    try {
      await createKnowledge(token, {
        type: values.type,
        key: values.key,
        title: values.title,
        content: values.content ?? "",
        locale: values.locale || undefined,
      });
      message.success("已创建草稿");
      onOpenChange(false);
      onSuccess();
    } catch (err) {
      message.error(err instanceof Error ? err.message : "创建失败");
    }
  }

  return (
    <Drawer
      title="新建知识条目"
      open={open}
      onClose={() => onOpenChange(false)}
      size="default"
    >
      <Form form={form} layout="vertical" onFinish={onSubmit}>
        <Form.Item
          name="type"
          label="类型"
          rules={[{ required: true }]}
        >
          <Select options={TYPES.map((t) => ({ value: t, label: t }))} />
        </Form.Item>
        <Form.Item
          name="key"
          label="Key"
          rules={[{ required: true, message: "Key 必填" }]}
        >
          <Input placeholder="错误码 / 路径 / slug" />
        </Form.Item>
        <Form.Item
          name="title"
          label="标题"
          rules={[{ required: true, message: "标题必填" }]}
        >
          <Input placeholder="条目标题" />
        </Form.Item>
        <Form.Item name="locale" label="语言（可选）">
          <Input placeholder="zh / en / …" />
        </Form.Item>
        <Form.Item name="content" label="内容（Markdown）">
          <TextArea
            rows={8}
            placeholder="Markdown 内容"
            style={{ fontFamily: "ui-monospace, monospace", fontSize: 13 }}
          />
        </Form.Item>
        <Form.Item style={{ marginBottom: 0 }}>
          <Flex justify="flex-end" gap="small">
            <Button onClick={() => onOpenChange(false)}>取消</Button>
            <Button type="primary" htmlType="submit">
              创建草稿
            </Button>
          </Flex>
        </Form.Item>
      </Form>
    </Drawer>
  );
}

export function KnowledgeRoute() {
  const { token, role } = useStaffSession();
  const { message, modal } = App.useApp();
  const allowed =
    role === "supervisor" || role === "engineer" || role === "admin";

  const [entries, setEntries] = useState<KnowledgeEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [search, setSearch] = useState("");

  function reload() {
    if (!token) return;
    setLoading(true);
    listKnowledge(token)
      .then(setEntries)
      .catch((e: unknown) =>
        setLoadError(e instanceof Error ? e.message : "加载失败"),
      )
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token || !allowed) {
      setLoadError("需要主管 / 工程师 / 管理员权限");
      setLoading(false);
      return;
    }
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role]);

  async function handlePublish(e: KnowledgeEntry) {
    if (!token) return;
    try {
      await publishKnowledge(token, e.id);
      message.success("已发布");
      reload();
    } catch (err) {
      message.error(err instanceof Error ? err.message : "发布失败");
    }
  }

  function handleDelete(e: KnowledgeEntry) {
    modal.confirm({
      title: `确认删除"${e.title}"？`,
      content: "此操作不可撤销。",
      okText: "删除",
      okType: "danger",
      cancelText: "取消",
      onOk: async () => {
        if (!token) return;
        try {
          await deleteKnowledge(token, e.id);
          message.success("已删除");
          reload();
        } catch (err) {
          message.error(err instanceof Error ? err.message : "删除失败");
        }
      },
    });
  }

  const columns: ColumnsType<KnowledgeEntry> = useMemo(
    () => [
      {
        title: "类型",
        dataIndex: "type",
        width: 120,
        render: (v: string) => (
          <Tag style={{ fontFamily: "ui-monospace, monospace" }}>{v}</Tag>
        ),
      },
      {
        title: "Key",
        dataIndex: "key",
        render: (v: string) => (
          <span style={{ fontFamily: "ui-monospace, monospace", fontSize: 13 }}>
            {v}
          </span>
        ),
      },
      {
        title: "标题",
        dataIndex: "title",
        sorter: (a, b) => a.title.localeCompare(b.title),
      },
      {
        title: "状态",
        dataIndex: "status",
        width: 100,
        render: (s: string) =>
          s === "published" ? <Tag color="green">已发布</Tag> : <Tag>草稿</Tag>,
      },
      {
        title: "来源",
        dataIndex: "source_gap_signal",
        render: (v: string | null) => v ?? "—",
      },
      {
        title: "更新时间",
        dataIndex: "updated_at",
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
        render: (_: unknown, e: KnowledgeEntry) => (
          <Dropdown
            menu={{
              items: [
                ...(e.status === "draft"
                  ? [
                      { key: "publish", label: "发布", onClick: () => handlePublish(e) },
                      { type: "divider" as const },
                    ]
                  : []),
                {
                  key: "delete",
                  label: "删除",
                  danger: true,
                  onClick: () => handleDelete(e),
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

  const filteredEntries = useMemo(() => {
    const kw = search.trim().toLowerCase();
    return kw
      ? entries.filter((e) => e.title.toLowerCase().includes(kw))
      : entries;
  }, [entries, search]);

  return (
    <div className="space-y-4 p-6">
      <Flex justify="space-between" align="flex-start" wrap="wrap" gap="middle">
        <Title level={3} style={{ margin: 0 }}>
          知识库
        </Title>
        {allowed && (
          <Button type="primary" onClick={() => setDrawerOpen(true)}>
            新建条目
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
              placeholder="搜索标题…"
              allowClear
              style={{ width: 240 }}
              onChange={(e) => setSearch(e.target.value)}
            />
          </Flex>
          <Table<KnowledgeEntry>
            rowKey="id"
            size="middle"
            columns={columns}
            dataSource={filteredEntries}
            pagination={{ pageSize: 20, showSizeChanger: true }}
            locale={{ emptyText: "暂无知识条目" }}
            scroll={{ x: "max-content" }}
          />
        </Card>
      )}

      {token && allowed && (
        <KnowledgeDrawer
          open={drawerOpen}
          onOpenChange={setDrawerOpen}
          token={token}
          onSuccess={reload}
        />
      )}
    </div>
  );
}
