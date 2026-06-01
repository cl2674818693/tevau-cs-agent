import {
  ArrowLeftOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  ForkOutlined,
  TeamOutlined,
} from "@ant-design/icons";
import {
  Alert,
  Breadcrumb,
  Button,
  Card,
  DatePicker,
  Flex,
  Skeleton,
  Space,
  Statistic,
  Table,
  Tabs,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import type { Dayjs } from "dayjs";
import dayjs from "dayjs";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  getPerformance,
  listPerformance,
  listStaffConversations,
  listStaffQaReviews,
  type StaffConversation,
  type StaffKpiRow,
  type StaffPerformance,
  type StaffQaReview,
} from "../../api/adminStaffPerformance";
import { useStaffSession } from "../../hooks/useStaffSession";

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;

function toUtcParam(d: Dayjs): string {
  return d.toDate().toISOString().slice(0, 19).replace("T", " ");
}

function fmtSeconds(s: number): string {
  if (s < 60) return `${Math.round(s)}s`;
  const m = Math.floor(s / 60);
  const sec = Math.round(s % 60);
  return `${m}m ${sec}s`;
}

function fmtPct(r: number): string {
  return `${(r * 100).toFixed(1)}%`;
}

// ── Overview (列表页) ─────────────────────────────────────────────────────────

function OverviewKpiCards({
  loading,
  team,
}: {
  loading: boolean;
  team: { staff_count: number; total_takeovers: number; total_resolved: number; total_transfers: number; avg_handle_seconds: number } | undefined;
}) {
  if (loading) {
    return (
      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Card key={i}>
            <Skeleton active paragraph={{ rows: 1 }} />
          </Card>
        ))}
      </div>
    );
  }
  if (!team) return null;
  return (
    <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
      <Card>
        <Statistic title="客服人数" value={team.staff_count} prefix={<TeamOutlined />} />
      </Card>
      <Card>
        <Statistic
          title="总接管数"
          value={team.total_takeovers}
          prefix={<CheckCircleOutlined />}
        />
      </Card>
      <Card>
        <Statistic
          title="总解决数"
          value={team.total_resolved}
          prefix={<CheckCircleOutlined />}
        />
      </Card>
      <Card>
        <Statistic
          title="团队平均处理时长"
          value={fmtSeconds(team.avg_handle_seconds)}
          prefix={<ClockCircleOutlined />}
        />
      </Card>
    </div>
  );
}

function StaffPerformanceOverview() {
  const { token, role } = useStaffSession();
  const allowed = role === "supervisor" || role === "admin";

  const [range, setRange] = useState<[Dayjs, Dayjs] | null>([
    dayjs().subtract(30, "day"),
    dayjs(),
  ]);
  const [data, setData] = useState<
    | {
        staff: StaffKpiRow[];
        team: {
          staff_count: number;
          total_takeovers: number;
          total_resolved: number;
          total_transfers: number;
          avg_handle_seconds: number;
        };
      }
    | null
  >(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!token) return;
    if (!allowed) {
      setErr("需要主管或管理员权限");
      setLoading(false);
      return;
    }
    setLoading(true);
    setErr("");
    const opts: { from?: string; to?: string } = {};
    if (range?.[0]) opts.from = toUtcParam(range[0]);
    if (range?.[1]) opts.to = toUtcParam(range[1]);
    listPerformance(token, opts)
      .then((res) => setData({ staff: res.staff, team: res.team }))
      .catch(() => setErr("加载失败"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role, range]);

  const columns: ColumnsType<StaffKpiRow> = useMemo(
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
        title: "接管数",
        dataIndex: "takeovers",
        sorter: (a, b) => a.takeovers - b.takeovers,
      },
      {
        title: "解决数",
        dataIndex: "resolved",
        sorter: (a, b) => a.resolved - b.resolved,
      },
      {
        title: "转派数",
        dataIndex: "transfers",
        sorter: (a, b) => a.transfers - b.transfers,
      },
      {
        title: "转派率",
        dataIndex: "transfer_ratio",
        sorter: (a, b) => a.transfer_ratio - b.transfer_ratio,
        render: (v: number) => fmtPct(v),
      },
      {
        title: "平均处理时长",
        dataIndex: "avg_handle_seconds",
        sorter: (a, b) => a.avg_handle_seconds - b.avg_handle_seconds,
        render: (v: number) => fmtSeconds(v),
      },
      {
        title: "",
        key: "actions",
        width: 100,
        align: "right",
        render: (_: unknown, row: StaffKpiRow) => (
          <Link to={`/admin/performance/${row.staff_id}`}>
            <Button type="link" size="small" style={{ padding: 0 }}>
              查看详情
            </Button>
          </Link>
        ),
      },
    ],
    [],
  );

  return (
    <div className="space-y-4 p-6">
      <Flex justify="space-between" align="flex-start" wrap="wrap" gap="middle">
        <Title level={3} style={{ margin: 0 }}>
          客服绩效
        </Title>
        <RangePicker
          value={range}
          onChange={(v) => setRange(v as [Dayjs, Dayjs] | null)}
          allowClear={false}
        />
      </Flex>

      {err && <Alert type="error" showIcon title={err} />}

      <OverviewKpiCards loading={loading} team={data?.team} />

      {!loading && allowed && data && (
        <Card>
          <Table<StaffKpiRow>
            rowKey="staff_id"
            size="middle"
            columns={columns}
            dataSource={data.staff}
            pagination={{ pageSize: 20, showSizeChanger: true }}
            locale={{ emptyText: "暂无数据" }}
          />
        </Card>
      )}
    </div>
  );
}

// ── Detail (单客服) ───────────────────────────────────────────────────────────

function OverviewTab({ p }: { p: StaffPerformance }) {
  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-2">
        <Card>
          <Statistic
            title="满意度"
            value={p.satisfaction.avg_rating}
            precision={1}
          />
          <Text type="secondary" style={{ fontSize: 12 }}>
            共 {p.satisfaction.count} 条评价
          </Text>
        </Card>
        <Card>
          <Statistic title="质检均分" value={p.qa.avg_score} precision={1} />
          <Text type="secondary" style={{ fontSize: 12 }}>
            共 {p.qa.count} 次质检
          </Text>
        </Card>
      </div>
      <div className="grid gap-3 md:grid-cols-3">
        <Card>
          <Statistic title="解决率" value={fmtPct(p.resolved_ratio)} />
        </Card>
        <Card>
          <Statistic title="转派率" value={fmtPct(p.transfer_ratio)} />
        </Card>
        <Card>
          <Statistic title="释放率" value={fmtPct(p.release_ratio)} />
        </Card>
      </div>
    </div>
  );
}

function StaffPerformanceDetail({ staffId }: { staffId: string }) {
  const { token, role } = useStaffSession();
  const allowed = role === "supervisor" || role === "admin";

  const [range, setRange] = useState<[Dayjs, Dayjs] | null>([
    dayjs().subtract(30, "day"),
    dayjs(),
  ]);
  const [p, setP] = useState<StaffPerformance | null>(null);
  const [convs, setConvs] = useState<StaffConversation[]>([]);
  const [qaReviews, setQaReviews] = useState<StaffQaReview[]>([]);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    if (!allowed) {
      setErr("需要主管或管理员权限");
      setLoading(false);
      return;
    }
    setLoading(true);
    setErr("");
    const opts: { from?: string; to?: string } = {};
    if (range?.[0]) opts.from = toUtcParam(range[0]);
    if (range?.[1]) opts.to = toUtcParam(range[1]);
    Promise.all([
      getPerformance(token, staffId, opts),
      listStaffConversations(token, staffId, opts),
      listStaffQaReviews(token, staffId, opts),
    ])
      .then(([perf, convRows, qaRows]) => {
        setP(perf);
        setConvs(convRows);
        setQaReviews(qaRows);
      })
      .catch(() => setErr("加载失败"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role, staffId, range]);

  const convColumns: ColumnsType<StaffConversation> = useMemo(
    () => [
      {
        title: "会话 ID",
        dataIndex: "id",
        sorter: (a, b) => a.id - b.id,
        render: (id: number) => (
          <Link
            to={`/admin/conversations/${id}`}
            style={{
              fontFamily: "ui-monospace, monospace",
              fontSize: 12,
            }}
          >
            #{id}
          </Link>
        ),
      },
      { title: "用户类型", dataIndex: "user_type", width: 100 },
      { title: "状态", dataIndex: "status", width: 120 },
      { title: "模式", dataIndex: "mode", width: 120 },
      { title: "创建时间", dataIndex: "created_at" },
      {
        title: "接管时间",
        dataIndex: "assigned_at",
        render: (v: string | null) => v ?? "—",
      },
    ],
    [],
  );

  const qaColumns: ColumnsType<StaffQaReview> = useMemo(
    () => [
      {
        title: "记录 ID",
        dataIndex: "review_id",
        width: 100,
        render: (v: number) => (
          <span style={{ fontFamily: "ui-monospace, monospace", fontSize: 12 }}>
            #{v}
          </span>
        ),
      },
      {
        title: "会话 ID",
        dataIndex: "conv_id",
        width: 100,
        render: (id: number) => (
          <Link
            to={`/admin/conversations/${id}`}
            style={{ fontFamily: "ui-monospace, monospace", fontSize: 12 }}
          >
            #{id}
          </Link>
        ),
      },
      {
        title: "评分卡",
        dataIndex: "scorecard_name",
        render: (v: string | null) => v ?? "—",
      },
      { title: "总分", dataIndex: "total_score", width: 100 },
      {
        title: "标签",
        dataIndex: "verdict",
        render: (v: string | null) => v ?? "—",
      },
      { title: "质检员", dataIndex: "reviewer_staff_id", width: 120 },
      { title: "质检时间", dataIndex: "created_at" },
    ],
    [],
  );

  return (
    <div className="space-y-4 p-6">
      <Breadcrumb
        items={[
          { title: <Link to="/admin/performance">客服绩效</Link> },
          { title: <span style={{ fontWeight: 500 }}>{staffId}</span> },
        ]}
      />

      <Flex justify="space-between" align="flex-start" wrap="wrap" gap="middle">
        <Title level={3} style={{ margin: 0 }}>
          客服绩效 — {staffId}
        </Title>
        <Space>
          <Link to="/admin/performance">
            <Button icon={<ArrowLeftOutlined />}>返回</Button>
          </Link>
          <RangePicker
            value={range}
            onChange={(v) => setRange(v as [Dayjs, Dayjs] | null)}
            allowClear={false}
          />
        </Space>
      </Flex>

      {err && <Alert type="error" showIcon title={err} />}

      {loading ? (
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}>
              <Skeleton active paragraph={{ rows: 1 }} />
            </Card>
          ))}
        </div>
      ) : p ? (
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
          <Card>
            <Statistic title="接管数" value={p.takeovers} prefix={<TeamOutlined />} />
          </Card>
          <Card>
            <Statistic
              title="解决数"
              value={p.resolved}
              prefix={<CheckCircleOutlined />}
            />
          </Card>
          <Card>
            <Statistic title="转派数" value={p.transfers} prefix={<ForkOutlined />} />
          </Card>
          <Card>
            <Statistic
              title="平均处理时长"
              value={fmtSeconds(p.avg_handle_seconds)}
              prefix={<ClockCircleOutlined />}
            />
          </Card>
        </div>
      ) : null}

      {!loading && p && (
        <Card>
          <Tabs
            defaultActiveKey="overview"
            items={[
              {
                key: "overview",
                label: "总览",
                children: <OverviewTab p={p} />,
              },
              {
                key: "conversations",
                label: "会话明细",
                children: (
                  <Table<StaffConversation>
                    rowKey="id"
                    size="small"
                    columns={convColumns}
                    dataSource={convs}
                    pagination={{ pageSize: 20, showSizeChanger: true }}
                    locale={{ emptyText: "无会话记录" }}
                  />
                ),
              },
              {
                key: "qa",
                label: "质检结果",
                children: (
                  <Table<StaffQaReview>
                    rowKey="review_id"
                    size="small"
                    columns={qaColumns}
                    dataSource={qaReviews}
                    pagination={{ pageSize: 20, showSizeChanger: true }}
                    locale={{ emptyText: "无质检记录" }}
                  />
                ),
              },
            ]}
          />
        </Card>
      )}
    </div>
  );
}

export function StaffPerformanceRoute() {
  const { staffId } = useParams();
  if (staffId) return <StaffPerformanceDetail staffId={staffId} />;
  return <StaffPerformanceOverview />;
}
