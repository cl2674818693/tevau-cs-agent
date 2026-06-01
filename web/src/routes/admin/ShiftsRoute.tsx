import { MoreOutlined } from "@ant-design/icons";
import {
  Alert,
  App,
  Button,
  Card,
  DatePicker,
  Drawer,
  Dropdown,
  Flex,
  Form,
  Input,
  Skeleton,
  Table,
  TimePicker,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { format } from "date-fns";
import dayjs, { type Dayjs } from "dayjs";
import { useEffect, useMemo, useState } from "react";

import {
  createShift,
  deleteShift,
  listShifts,
  patchShift,
  type Shift,
} from "../../api/adminShifts";
import { useStaffSession } from "../../hooks/useStaffSession";

const { Title } = Typography;

type FormValues = {
  staff_id: string;
  start_date: Dayjs;
  start_time: Dayjs;
  end_date: Dayjs;
  end_time: Dayjs;
};

/** Build a UTC datetime string "YYYY-MM-DD HH:MM:SS" from antd date + time */
function buildDatetime(date: Dayjs, time: Dayjs): string {
  return `${date.format("YYYY-MM-DD")} ${time.format("HH:mm")}:00`;
}

function parseShiftDatetime(dt: string): { date: Dayjs; time: Dayjs } {
  // "YYYY-MM-DD HH:MM:SS" 后端返回 UTC；不引入 dayjs utc 插件，
  // 把字符串补 Z 后用 Date 解析，再走 dayjs 包装供 DatePicker/TimePicker 使用。
  // 显示按本地时区——与表单 buildDatetime 写回的格式一致（双向对齐）。
  const d = new Date(dt.replace(" ", "T") + (dt.endsWith("Z") ? "" : "Z"));
  const wrapped = dayjs(d);
  return { date: wrapped, time: wrapped };
}

/** 创建 + 编辑共用一个 Drawer：editing=null 即新建 */
function ShiftDrawer({
  open,
  onOpenChange,
  editing,
  token,
  onSuccess,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  editing: Shift | null;
  token: string;
  onSuccess: () => void;
}) {
  const [form] = Form.useForm<FormValues>();
  const { message } = App.useApp();

  useEffect(() => {
    if (open) {
      if (editing) {
        const s = parseShiftDatetime(editing.start_at);
        const e = parseShiftDatetime(editing.end_at);
        form.setFieldsValue({
          staff_id: editing.staff_id,
          start_date: s.date,
          start_time: s.time,
          end_date: e.date,
          end_time: e.time,
        });
      } else {
        form.setFieldsValue({
          staff_id: "",
          start_date: dayjs(),
          start_time: dayjs("09:00", "HH:mm"),
          end_date: dayjs(),
          end_time: dayjs("18:00", "HH:mm"),
        });
      }
    }
  }, [open, editing, form]);

  async function onSubmit(values: FormValues) {
    try {
      const payload = {
        staff_id: values.staff_id,
        start_at: buildDatetime(values.start_date, values.start_time),
        end_at: buildDatetime(values.end_date, values.end_time),
      };
      if (editing) {
        await patchShift(token, editing.id, payload);
        message.success("排班已更新");
      } else {
        await createShift(token, payload);
        message.success("排班已创建");
      }
      onOpenChange(false);
      onSuccess();
    } catch (err) {
      message.error(err instanceof Error ? err.message : "保存失败");
    }
  }

  return (
    <Drawer
      title={editing ? `编辑排班 #${editing.id}` : "新建排班"}
      open={open}
      onClose={() => onOpenChange(false)}
      size="default"
    >
      <Form form={form} layout="vertical" onFinish={onSubmit}>
        <Form.Item
          name="staff_id"
          label="Staff ID"
          rules={[{ required: true, message: "staff_id 必填" }]}
        >
          <Input placeholder="staff_id" />
        </Form.Item>
        <Form.Item
          name="start_date"
          label="开始日期"
          rules={[{ required: true }]}
        >
          <DatePicker style={{ width: "100%" }} placeholder="选择开始日期" />
        </Form.Item>
        <Form.Item
          name="start_time"
          label="开始时间（HH:mm）"
          rules={[{ required: true }]}
        >
          <TimePicker format="HH:mm" style={{ width: "100%" }} />
        </Form.Item>
        <Form.Item
          name="end_date"
          label="结束日期"
          rules={[{ required: true }]}
        >
          <DatePicker style={{ width: "100%" }} placeholder="选择结束日期" />
        </Form.Item>
        <Form.Item
          name="end_time"
          label="结束时间（HH:mm）"
          rules={[{ required: true }]}
        >
          <TimePicker format="HH:mm" style={{ width: "100%" }} />
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

export function ShiftsRoute() {
  const { token, role } = useStaffSession();
  const { message, modal } = App.useApp();
  const allowed = role === "supervisor" || role === "admin";
  const [shifts, setShifts] = useState<Shift[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<Shift | null>(null);
  const [search, setSearch] = useState("");

  function reload() {
    if (!token) return;
    setLoading(true);
    listShifts(token)
      .then(setShifts)
      .catch((e: unknown) =>
        setLoadError(e instanceof Error ? e.message : "加载失败"),
      )
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token) return;
    if (!allowed) {
      setLoadError("需要主管或管理员权限");
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

  function openEdit(s: Shift) {
    setEditing(s);
    setDrawerOpen(true);
  }

  function handleDelete(s: Shift) {
    modal.confirm({
      title: `确认删除排班 #${s.id}？`,
      content: `staff_id: ${s.staff_id}（此操作不可撤销）`,
      okText: "删除",
      okType: "danger",
      cancelText: "取消",
      onOk: async () => {
        if (!token) return;
        try {
          await deleteShift(token, s.id);
          message.success("已删除");
          reload();
        } catch (err) {
          message.error(err instanceof Error ? err.message : "删除失败");
        }
      },
    });
  }

  const columns: ColumnsType<Shift> = useMemo(
    () => [
      {
        title: "ID",
        dataIndex: "id",
        width: 80,
        sorter: (a, b) => a.id - b.id,
      },
      {
        title: "Staff ID",
        dataIndex: "staff_id",
        sorter: (a, b) => a.staff_id.localeCompare(b.staff_id),
      },
      {
        title: "开始时间",
        dataIndex: "start_at",
        render: (v: string) => {
          try {
            return format(new Date(v.replace(" ", "T") + "Z"), "yyyy-MM-dd HH:mm");
          } catch {
            return v;
          }
        },
      },
      {
        title: "结束时间",
        dataIndex: "end_at",
        render: (v: string) => {
          try {
            return format(new Date(v.replace(" ", "T") + "Z"), "yyyy-MM-dd HH:mm");
          } catch {
            return v;
          }
        },
      },
      {
        title: "创建时间",
        dataIndex: "created_at",
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
        render: (_: unknown, s: Shift) => (
          <Dropdown
            menu={{
              items: [
                { key: "edit", label: "编辑", onClick: () => openEdit(s) },
                { type: "divider" },
                {
                  key: "delete",
                  label: "删除",
                  danger: true,
                  onClick: () => handleDelete(s),
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

  const filteredShifts = useMemo(() => {
    const kw = search.trim().toLowerCase();
    return kw
      ? shifts.filter((s) => s.staff_id.toLowerCase().includes(kw))
      : shifts;
  }, [shifts, search]);

  return (
    <div className="space-y-4 p-6">
      <Flex justify="space-between" align="flex-start" wrap="wrap" gap="middle">
        <Title level={3} style={{ margin: 0 }}>
          排班
        </Title>
        {allowed && (
          <Button type="primary" onClick={openCreate}>
            新建排班
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
              placeholder="按 staff_id 搜索…"
              allowClear
              style={{ width: 240 }}
              onChange={(e) => setSearch(e.target.value)}
            />
          </Flex>
          <Table<Shift>
            rowKey="id"
            size="middle"
            columns={columns}
            dataSource={filteredShifts}
            pagination={{ pageSize: 20, showSizeChanger: true }}
            locale={{ emptyText: "暂无排班" }}
          />
        </Card>
      )}

      {token && allowed && (
        <ShiftDrawer
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
