import { ExportOutlined, ReloadOutlined } from "@ant-design/icons";
import {
  Alert,
  App,
  Button,
  Card,
  DatePicker,
  Drawer,
  Flex,
  Form,
  Input,
  InputNumber,
  Select,
  Skeleton,
  Space,
  Table,
  Tag,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import type { Dayjs } from "dayjs";
import { format } from "date-fns";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  listReviews,
  listScorecards,
  submitReview,
  type QaReview,
  type Scorecard,
} from "../../api/adminQa";
import { useStaffSession } from "../../hooks/useStaffSession";

const { Title } = Typography;
const { RangePicker } = DatePicker;
const { TextArea } = Input;

function formatDateTime(val: string) {
  try {
    return format(new Date(val), "yyyy-MM-dd HH:mm:ss");
  } catch {
    return val;
  }
}

function scoreColor(score: number): string | undefined {
  if (score >= 90) return "green";
  if (score >= 70) return undefined;
  return "red";
}

interface ReviewDrawerProps {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  scorecards: Scorecard[];
  defaultConvId?: number;
  token: string;
  onSuccess: () => void;
}

function ReviewDrawer({
  open,
  onOpenChange,
  scorecards,
  defaultConvId,
  token,
  onSuccess,
}: ReviewDrawerProps) {
  const [form] = Form.useForm<{
    conversation_id: number;
    scorecard_id: number;
    score: number;
    tags?: string;
    comment?: string;
  }>();
  const { message } = App.useApp();
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open) {
      form.setFieldsValue({
        conversation_id: defaultConvId ?? 0,
        scorecard_id: scorecards[0]?.id ?? 0,
        score: 80,
        tags: "",
        comment: "",
      });
    }
  }, [open, defaultConvId, scorecards, form]);

  async function onSubmit(values: {
    conversation_id: number;
    scorecard_id: number;
    score: number;
    tags?: string;
    comment?: string;
  }) {
    setSubmitting(true);
    try {
      await submitReview(token, {
        conversation_id: values.conversation_id,
        scorecard_id: values.scorecard_id,
        score: values.score,
        items_result: {},
        tags: values.tags || undefined,
        comment: values.comment || undefined,
      });
      message.success("质检已提交");
      onOpenChange(false);
      onSuccess();
    } catch (e) {
      message.error(e instanceof Error ? e.message : "提交失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Drawer
      title="提交质检"
      open={open}
      onClose={() => onOpenChange(false)}
      size="default"
    >
      <Form form={form} layout="vertical" onFinish={onSubmit}>
        <Form.Item
          name="conversation_id"
          label="会话 ID"
          rules={[{ required: true, type: "number", min: 1 }]}
        >
          <InputNumber min={1} style={{ width: "100%" }} placeholder="输入会话 ID" />
        </Form.Item>
        <Form.Item
          name="scorecard_id"
          label="评分卡"
          rules={[{ required: true, type: "number", min: 1, message: "请选择评分卡" }]}
        >
          <Select
            placeholder="选择评分卡"
            options={scorecards.map((s) => ({ value: s.id, label: s.name }))}
          />
        </Form.Item>
        <Form.Item
          name="score"
          label="得分（0–100）"
          rules={[{ required: true, type: "number", min: 0, max: 100 }]}
        >
          <InputNumber min={0} max={100} style={{ width: "100%" }} />
        </Form.Item>
        <Form.Item name="tags" label="标签">
          <Input placeholder="excellent / violation / …" />
        </Form.Item>
        <Form.Item name="comment" label="备注">
          <TextArea rows={3} placeholder="可选备注" />
        </Form.Item>
        <Form.Item style={{ marginBottom: 0 }}>
          <Flex justify="flex-end" gap="small">
            <Button onClick={() => onOpenChange(false)}>取消</Button>
            <Button type="primary" htmlType="submit" loading={submitting}>
              提交质检
            </Button>
          </Flex>
        </Form.Item>
      </Form>
    </Drawer>
  );
}

interface FilterState {
  dateRange: [Dayjs | null, Dayjs | null] | null;
}

export function QaReviewRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "supervisor" || role === "admin";

  const [reviews, setReviews] = useState<QaReview[]>([]);
  const [scorecards, setScorecards] = useState<Scorecard[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [filter, setFilter] = useState<FilterState>({ dateRange: null });
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerConvId, setDrawerConvId] = useState<number | undefined>(undefined);
  const [search, setSearch] = useState("");

  function reload(f: FilterState = filter) {
    if (!token) return;
    setLoading(true);
    setErr("");
    Promise.all([listScorecards(token, true), listReviews(token)])
      .then(([sc, rv]) => {
        setScorecards(sc);
        const from = f.dateRange?.[0]?.startOf("day").valueOf() ?? null;
        const to = f.dateRange?.[1]?.endOf("day").valueOf() ?? null;
        const filtered =
          from != null || to != null
            ? rv.filter((r) => {
                const t = new Date(r.created_at).getTime();
                if (from != null && t < from) return false;
                if (to != null && t > to) return false;
                return true;
              })
            : rv;
        const sorted = [...filtered].sort(
          (a, b) =>
            new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
        );
        setReviews(sorted);
      })
      .catch(() => setErr("加载失败，请重试"))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token) return;
    if (!allowed) {
      setErr("需要主管或管理员权限");
      setLoading(false);
      return;
    }
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role]);

  function openReviewDrawer(row?: QaReview) {
    setDrawerConvId(row?.conversation_id);
    setDrawerOpen(true);
  }

  const columns: ColumnsType<QaReview> = useMemo(
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
        title: "会话",
        dataIndex: "conversation_id",
        width: 100,
        sorter: (a, b) => a.conversation_id - b.conversation_id,
        render: (id: number) => (
          <span style={{ fontFamily: "ui-monospace, monospace", fontSize: 12 }}>
            #{id}
          </span>
        ),
      },
      {
        title: "质检员",
        dataIndex: "reviewer_staff_id",
        width: 120,
        render: (v: string) => (
          <span style={{ fontFamily: "ui-monospace, monospace", fontSize: 12 }}>
            {v}
          </span>
        ),
      },
      {
        title: "得分",
        dataIndex: "score",
        width: 100,
        sorter: (a, b) => a.score - b.score,
        render: (s: number) => <Tag color={scoreColor(s)}>{s}</Tag>,
      },
      {
        title: "标签",
        dataIndex: "tags",
        render: (v: string | null) =>
          v ? (
            <span style={{ fontSize: 12, color: "rgba(0,0,0,0.65)" }}>{v}</span>
          ) : (
            <span style={{ color: "rgba(0,0,0,0.45)" }}>—</span>
          ),
      },
      {
        title: "备注",
        dataIndex: "comment",
        render: (v: string | null) =>
          v ? (
            <span style={{ fontSize: 12, color: "rgba(0,0,0,0.65)" }}>{v}</span>
          ) : (
            <span style={{ color: "rgba(0,0,0,0.45)" }}>—</span>
          ),
      },
      {
        title: "",
        key: "actions",
        width: 180,
        render: (_: unknown, row: QaReview) => (
          <Space size="middle">
            <Link to={`/staff/conversations/${row.conversation_id}/logs`}>
              <Button type="link" size="small" icon={<ExportOutlined />} style={{ padding: 0 }}>
                查看
              </Button>
            </Link>
            <Button
              type="link"
              size="small"
              style={{ padding: 0 }}
              onClick={() => openReviewDrawer(row)}
            >
              重新质检
            </Button>
          </Space>
        ),
      },
    ],
    [],
  );

  const filteredRows = useMemo(() => {
    const kw = search.trim();
    return kw
      ? reviews.filter((r) => String(r.conversation_id).includes(kw))
      : reviews;
  }, [reviews, search]);

  return (
    <div className="space-y-4 p-6">
      <Flex justify="space-between" align="flex-start" wrap="wrap" gap="middle">
        <Title level={3} style={{ margin: 0 }}>
          会话质检
        </Title>
        <Space>
          <Button
            icon={<ReloadOutlined spin={loading} />}
            onClick={() => reload()}
            disabled={loading}
          >
            刷新
          </Button>
          {allowed && (
            <Button type="primary" onClick={() => openReviewDrawer()}>
              新建质检
            </Button>
          )}
        </Space>
      </Flex>

      {err && <Alert type="error" showIcon title={err} />}

      {allowed && (
        <Card>
          <Space wrap style={{ marginBottom: 12 }}>
            <Input.Search
              placeholder="搜索会话 ID…"
              allowClear
              style={{ width: 200 }}
              onChange={(e) => setSearch(e.target.value)}
            />
            <RangePicker
              value={filter.dateRange}
              onChange={(v) =>
                setFilter({ dateRange: v as [Dayjs | null, Dayjs | null] | null })
              }
            />
            <Button type="primary" onClick={() => reload(filter)} disabled={loading}>
              筛选
            </Button>
            {filter.dateRange && (
              <Button
                type="text"
                onClick={() => {
                  const next = { dateRange: null };
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
            <Table<QaReview>
              rowKey={(r) =>
                `${r.conversation_id}-${r.reviewer_staff_id}-${r.created_at}`
              }
              size="small"
              columns={columns}
              dataSource={filteredRows}
              pagination={{ pageSize: 20, showSizeChanger: true }}
              locale={{ emptyText: "暂无质检记录" }}
            />
          )}
        </Card>
      )}

      {token && (
        <ReviewDrawer
          open={drawerOpen}
          onOpenChange={setDrawerOpen}
          scorecards={scorecards}
          defaultConvId={drawerConvId}
          token={token}
          onSuccess={() => reload()}
        />
      )}
    </div>
  );
}
