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
  Modal,
  Select,
  Skeleton,
  Switch,
  Table,
  Tag,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { format } from "date-fns";
import { useEffect, useMemo, useState } from "react";

import {
  createStaff,
  listStaff,
  patchStaff,
  resetPassword,
  STAFF_ROLES,
  type StaffRow,
} from "../../api/adminStaff";
import { listGroups, type StaffGroup } from "../../api/adminStaffGroups";
import { useStaffSession } from "../../hooks/useStaffSession";

const { Title } = Typography;

const ROLE_LABEL: Record<string, string> = {
  agent: "客服",
  senior: "高级",
  supervisor: "主管",
  engineer: "工程",
  manager: "经理",
  admin: "管理员",
};

function parseSkills(raw: string | null): string[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed))
      return parsed.filter((s) => typeof s === "string");
    return [];
  } catch {
    return [];
  }
}

function formatDate(val: string) {
  try {
    return format(new Date(val), "yyyy-MM-dd HH:mm");
  } catch {
    return val;
  }
}

// ── Create Drawer ────────────────────────────────────────────────────────────

type CreateValues = {
  staff_id: string;
  display_name: string;
  role: (typeof STAFF_ROLES)[number];
  password: string;
};

function CreateDrawer({
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
  const [form] = Form.useForm<CreateValues>();
  const { message } = App.useApp();

  useEffect(() => {
    if (open) {
      form.setFieldsValue({
        staff_id: "",
        display_name: "",
        role: "agent",
        password: "",
      });
    }
  }, [open, form]);

  async function onSubmit(values: CreateValues) {
    try {
      await createStaff(token, values);
      message.success("已创建");
      onOpenChange(false);
      onSuccess();
    } catch (err) {
      message.error(err instanceof Error ? err.message : "创建失败");
    }
  }

  return (
    <Drawer
      title="新建客服"
      open={open}
      onClose={() => onOpenChange(false)}
      size="default"
    >
      <Form form={form} layout="vertical" onFinish={onSubmit}>
        <Form.Item
          name="staff_id"
          label="staff_id"
          rules={[
            { required: true, message: "staff_id 必填" },
            {
              pattern: /^[a-z][a-z0-9_]*$/,
              message: "小写字母开头，仅含小写字母+数字+下划线",
            },
          ]}
        >
          <Input placeholder="小写字母开头" />
        </Form.Item>
        <Form.Item
          name="display_name"
          label="显示名"
          rules={[{ required: true, message: "显示名必填" }]}
        >
          <Input placeholder="显示名" />
        </Form.Item>
        <Form.Item name="role" label="角色" rules={[{ required: true }]}>
          <Select
            options={STAFF_ROLES.map((r) => ({
              value: r,
              label: ROLE_LABEL[r] ?? r,
            }))}
          />
        </Form.Item>
        <Form.Item
          name="password"
          label="初始密码"
          rules={[{ required: true, min: 8, message: "密码至少 8 位" }]}
        >
          <Input.Password placeholder="至少 8 位" />
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

// ── Edit Drawer ──────────────────────────────────────────────────────────────

type EditValues = {
  display_name: string;
  role: (typeof STAFF_ROLES)[number];
  group_id: string; // "__none__" | stringified number
  skills: string; // comma-separated
  active: boolean;
};

function EditDrawer({
  open,
  onOpenChange,
  staff,
  groups,
  token,
  onSuccess,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  staff: StaffRow | null;
  groups: StaffGroup[];
  token: string;
  onSuccess: () => void;
}) {
  const [form] = Form.useForm<EditValues>();
  const { message } = App.useApp();

  useEffect(() => {
    if (open && staff) {
      form.setFieldsValue({
        display_name: staff.display_name,
        role: staff.role as EditValues["role"],
        group_id: staff.group_id != null ? String(staff.group_id) : "__none__",
        skills: parseSkills(staff.skills).join(", "),
        active: staff.active === 1,
      });
    }
  }, [open, staff, form]);

  async function onSubmit(values: EditValues) {
    if (!staff) return;
    try {
      const skillsArr = values.skills
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const groupId =
        values.group_id === "__none__" ? null : Number(values.group_id);

      await patchStaff(token, staff.staff_id, {
        display_name: values.display_name,
        role: values.role,
        group_id: groupId,
        skills: skillsArr,
        active: values.active ? 1 : 0,
      });
      message.success("已保存");
      onOpenChange(false);
      onSuccess();
    } catch (err) {
      message.error(err instanceof Error ? err.message : "保存失败");
    }
  }

  return (
    <Drawer
      title={`编辑客服 ${staff?.staff_id ?? ""}`}
      open={open}
      onClose={() => onOpenChange(false)}
      size="default"
    >
      <Form form={form} layout="vertical" onFinish={onSubmit}>
        <Form.Item
          name="display_name"
          label="显示名"
          rules={[{ required: true, message: "显示名必填" }]}
        >
          <Input placeholder="显示名" />
        </Form.Item>
        <Form.Item name="role" label="角色" rules={[{ required: true }]}>
          <Select
            options={STAFF_ROLES.map((r) => ({
              value: r,
              label: ROLE_LABEL[r] ?? r,
            }))}
          />
        </Form.Item>
        <Form.Item name="group_id" label="分组">
          <Select
            options={[
              { value: "__none__", label: "无" },
              ...groups.map((g) => ({ value: String(g.id), label: g.name })),
            ]}
          />
        </Form.Item>
        <Form.Item name="skills" label="技能（逗号分隔）">
          <Input placeholder="如: 英语, 理财" />
        </Form.Item>
        <Form.Item name="active" label="启用" valuePropName="checked">
          <Switch />
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

// ── Reset Password Modal ─────────────────────────────────────────────────────

function ResetPasswordModal({
  open,
  onOpenChange,
  staffId,
  token,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  staffId: string | null;
  token: string;
}) {
  const [form] = Form.useForm<{ password: string }>();
  const { message } = App.useApp();

  useEffect(() => {
    if (open) form.setFieldsValue({ password: "" });
  }, [open, form]);

  async function onSubmit(values: { password: string }) {
    if (!staffId) return;
    try {
      await resetPassword(token, staffId, values.password);
      message.success("密码已重置");
      onOpenChange(false);
    } catch (err) {
      message.error(err instanceof Error ? err.message : "重置失败");
    }
  }

  return (
    <Modal
      title={`重置密码 — ${staffId ?? ""}`}
      open={open}
      onCancel={() => onOpenChange(false)}
      onOk={() => form.submit()}
      okText="确认重置"
      cancelText="取消"
      destroyOnHidden
    >
      <Form form={form} layout="vertical" onFinish={onSubmit}>
        <Form.Item
          name="password"
          label="新密码"
          rules={[{ required: true, min: 8, message: "密码至少 8 位" }]}
        >
          <Input.Password placeholder="至少 8 位" />
        </Form.Item>
      </Form>
    </Modal>
  );
}

// ── Route ────────────────────────────────────────────────────────────────────

export function StaffAccountsRoute() {
  const { token } = useStaffSession();
  const { message } = App.useApp();
  const [rows, setRows] = useState<StaffRow[]>([]);
  const [groups, setGroups] = useState<StaffGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<StaffRow | null>(null);
  const [resetPwOpen, setResetPwOpen] = useState(false);
  const [resetPwTarget, setResetPwTarget] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  function reload() {
    if (!token) return;
    setLoading(true);
    Promise.all([listStaff(token), listGroups(token)])
      .then(([rs, gs]) => {
        setRows(rs);
        setGroups(gs);
      })
      .catch((e: unknown) =>
        setLoadError(e instanceof Error ? e.message : "加载失败"),
      )
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  function openEdit(s: StaffRow) {
    setEditTarget(s);
    setEditOpen(true);
  }

  function openResetPw(staffId: string) {
    setResetPwTarget(staffId);
    setResetPwOpen(true);
  }

  async function handleToggleActive(s: StaffRow) {
    if (!token) return;
    try {
      await patchStaff(token, s.staff_id, {
        active: s.active === 1 ? 0 : 1,
      });
      reload();
    } catch (err) {
      message.error(err instanceof Error ? err.message : "操作失败");
    }
  }

  const groupMap = useMemo(
    () => new Map(groups.map((g) => [g.id, g.name])),
    [groups],
  );

  const columns: ColumnsType<StaffRow> = useMemo(
    () => [
      {
        title: "staff_id",
        dataIndex: "staff_id",
        sorter: (a, b) => a.staff_id.localeCompare(b.staff_id),
        render: (v: string) => (
          <span style={{ fontFamily: "ui-monospace, monospace", fontSize: 12 }}>
            {v}
          </span>
        ),
      },
      {
        title: "显示名",
        dataIndex: "display_name",
        sorter: (a, b) => a.display_name.localeCompare(b.display_name),
      },
      {
        title: "角色",
        dataIndex: "role",
        width: 100,
        render: (v: string) => <Tag>{ROLE_LABEL[v] ?? v}</Tag>,
      },
      {
        title: "分组",
        dataIndex: "group_id",
        render: (gid: number | null) => {
          if (gid == null)
            return <span style={{ color: "rgba(0,0,0,0.45)" }}>-</span>;
          return (
            groupMap.get(gid) ?? (
              <span style={{ color: "rgba(0,0,0,0.45)" }}>-</span>
            )
          );
        },
      },
      {
        title: "技能",
        dataIndex: "skills",
        render: (v: string | null) => {
          const skills = parseSkills(v);
          if (!skills.length)
            return <span style={{ color: "rgba(0,0,0,0.45)" }}>-</span>;
          return (
            <Flex wrap="wrap" gap={4}>
              {skills.map((sk) => (
                <Tag key={sk} style={{ marginRight: 0 }}>
                  {sk}
                </Tag>
              ))}
            </Flex>
          );
        },
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
        render: (v: string) => formatDate(v),
      },
      {
        title: "",
        key: "actions",
        width: 60,
        align: "right",
        render: (_: unknown, s: StaffRow) => (
          <Dropdown
            menu={{
              items: [
                { key: "edit", label: "编辑", onClick: () => openEdit(s) },
                {
                  key: "resetpw",
                  label: "重置密码",
                  onClick: () => openResetPw(s.staff_id),
                },
                { type: "divider" },
                {
                  key: "toggle",
                  label: s.active ? "停用" : "启用",
                  onClick: () => handleToggleActive(s),
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
    [token, groupMap],
  );

  const filteredRows = useMemo(() => {
    const kw = search.trim().toLowerCase();
    return kw
      ? rows.filter((r) => r.staff_id.toLowerCase().includes(kw))
      : rows;
  }, [rows, search]);

  return (
    <div className="space-y-4 p-6">
      <Flex justify="space-between" align="flex-start" wrap="wrap" gap="middle">
        <Title level={3} style={{ margin: 0 }}>
          客服账号
        </Title>
        <Button type="primary" onClick={() => setCreateOpen(true)}>
          新建客服
        </Button>
      </Flex>

      {loadError && <Alert type="error" showIcon title={loadError} />}

      {loading ? (
        <Card>
          <Skeleton active paragraph={{ rows: 6 }} />
        </Card>
      ) : (
        <Card>
          <Flex style={{ marginBottom: 12 }}>
            <Input.Search
              placeholder="搜索 staff_id…"
              allowClear
              style={{ width: 240 }}
              onChange={(e) => setSearch(e.target.value)}
            />
          </Flex>
          <Table<StaffRow>
            rowKey="staff_id"
            size="middle"
            columns={columns}
            dataSource={filteredRows}
            pagination={{ pageSize: 20, showSizeChanger: true }}
            locale={{ emptyText: "暂无客服" }}
          />
        </Card>
      )}

      {token && (
        <>
          <CreateDrawer
            open={createOpen}
            onOpenChange={setCreateOpen}
            token={token}
            onSuccess={reload}
          />
          <EditDrawer
            open={editOpen}
            onOpenChange={setEditOpen}
            staff={editTarget}
            groups={groups}
            token={token}
            onSuccess={reload}
          />
          <ResetPasswordModal
            open={resetPwOpen}
            onOpenChange={setResetPwOpen}
            staffId={resetPwTarget}
            token={token}
          />
        </>
      )}
    </div>
  );
}
