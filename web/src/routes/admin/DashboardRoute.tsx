import {
  AlertOutlined,
  CommentOutlined,
  DislikeOutlined,
  ToolOutlined,
  UserSwitchOutlined,
} from "@ant-design/icons";
import {
  Alert,
  Card,
  DatePicker,
  Flex,
  Skeleton,
  Space,
  Statistic,
  Typography,
} from "antd";
import type { Dayjs } from "dayjs";
import dayjs from "dayjs";
import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { getOverview, type DashboardOverview } from "../../api/adminDashboard";
import { useStaffSession } from "../../hooks/useStaffSession";

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;

function toUtcParam(d: Dayjs): string {
  return d.toDate().toISOString().slice(0, 19).replace("T", " ");
}

function pct(x: number): string {
  return `${(x * 100).toFixed(1)}%`;
}

function buildBarData(d: DashboardOverview) {
  return [
    { name: "转人工", value: +(d.handoff_rate * 100).toFixed(1) },
    { name: "差评率", value: +(d.downvote_rate * 100).toFixed(1) },
    { name: "工具空结果", value: +(d.tool_empty_rate * 100).toFixed(1) },
  ];
}

function KpiSection({
  data,
  loading,
}: {
  data: DashboardOverview | null;
  loading: boolean;
}) {
  if (loading) {
    return (
      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <Card key={i}>
            <Skeleton active paragraph={{ rows: 1 }} />
          </Card>
        ))}
      </div>
    );
  }
  if (!data) return null;
  return (
    <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
      <Card>
        <Statistic
          title="会话总数"
          value={data.total_conversations}
          prefix={<CommentOutlined />}
        />
      </Card>
      <Card>
        <Statistic
          title={`转人工数 · ${pct(data.handoff_rate)}`}
          value={data.handoff}
          valueStyle={{ color: data.handoff_rate > 0.3 ? "#dc2626" : undefined }}
          prefix={<UserSwitchOutlined />}
        />
      </Card>
      <Card>
        <Statistic
          title={`差评数 · ${pct(data.downvote_rate)}`}
          value={data.downvote}
          valueStyle={{ color: data.downvote_rate > 0.2 ? "#dc2626" : undefined }}
          prefix={<DislikeOutlined />}
        />
      </Card>
      <Card>
        <Statistic
          title={`工具空结果率 · ${data.tool_empty} / ${data.tool_calls} 次`}
          value={pct(data.tool_empty_rate)}
          valueStyle={{
            color: data.tool_empty_rate > 0.3 ? "#dc2626" : undefined,
          }}
          prefix={<ToolOutlined />}
        />
      </Card>
      <Card>
        <Statistic
          title="超范围提问"
          value={data.out_of_scope}
          prefix={<AlertOutlined />}
        />
      </Card>
      <Card>
        <Statistic
          title="失败回合"
          value={data.failed_turns}
          valueStyle={{ color: data.failed_turns > 0 ? "#dc2626" : undefined }}
          prefix={<AlertOutlined />}
        />
      </Card>
    </div>
  );
}

export function DashboardRoute() {
  const { token, role } = useStaffSession();
  const allowed =
    role === "supervisor" || role === "manager" || role === "admin";

  const [range, setRange] = useState<[Dayjs, Dayjs] | null>([
    dayjs().subtract(7, "day"),
    dayjs(),
  ]);
  const [d, setD] = useState<DashboardOverview | null>(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token || !allowed) {
      setErr("需要管理权限");
      setLoading(false);
      return;
    }
    setLoading(true);
    setErr("");
    const opts: { from?: string; to?: string } = {};
    if (range?.[0]) opts.from = toUtcParam(range[0]);
    if (range?.[1]) opts.to = toUtcParam(range[1]);
    getOverview(token, opts)
      .then(setD)
      .catch(() => setErr("加载失败"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role, range]);

  const barData = useMemo(() => (d ? buildBarData(d) : []), [d]);

  return (
    <div className="space-y-4 p-6">
      <Flex justify="space-between" align="flex-start" wrap="wrap" gap="middle">
        <Title level={3} style={{ margin: 0 }}>
          数据大盘
        </Title>
        <Space>
          <RangePicker
            value={range}
            onChange={(v) => setRange(v as [Dayjs, Dayjs] | null)}
            allowClear={false}
          />
        </Space>
      </Flex>

      {err && <Alert type="error" showIcon title={err} />}

      <KpiSection data={d} loading={loading} />

      {loading ? (
        <Card>
          <Skeleton active paragraph={{ rows: 8 }} />
        </Card>
      ) : (
        d && (
          <Card title="关键比率对比（%）" size="small">
            <ResponsiveContainer width="100%" height={300}>
              <BarChart
                data={barData}
                margin={{ top: 4, right: 16, left: 0, bottom: 4 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="name" tick={{ fontSize: 12 }} stroke="#6b7280" />
                <YAxis tick={{ fontSize: 12 }} stroke="#6b7280" unit="%" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#fff",
                    border: "1px solid #e5e7eb",
                    borderRadius: 8,
                  }}
                  formatter={(value) => [`${value}%`, ""]}
                />
                <Bar dataKey="value" fill="#4f46e5" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
            <Text type="secondary" className="mt-2 block text-xs">
              提示：当前 API 仅返回汇总值，柱状图为单点对比。后续接入时间序列后会替换为趋势图。
            </Text>
          </Card>
        )
      )}
    </div>
  );
}
