import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  SwapOutlined,
  UserSwitchOutlined,
} from "@ant-design/icons";
import {
  Alert,
  Card,
  DatePicker,
  Empty,
  Flex,
  Skeleton,
  Statistic,
  Typography,
} from "antd";
import type { Dayjs } from "dayjs";
import dayjs from "dayjs";
import { useEffect, useState } from "react";

import { getKpi, type StaffKpi } from "../../api/staff";
import { useStaffSession } from "../../hooks/useStaffSession";

const { Title } = Typography;
const { RangePicker } = DatePicker;

function toUtcParam(d: Dayjs): string {
  return d.toDate().toISOString().slice(0, 19).replace("T", " ");
}

function fmtDuration(seconds: number): string {
  if (seconds <= 0) return "-";
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m > 0 ? `${m}分${s}秒` : `${s}秒`;
}

export function KpiRoute() {
  const { token, staffId } = useStaffSession();

  const [range, setRange] = useState<[Dayjs, Dayjs] | null>([
    dayjs().subtract(7, "day"),
    dayjs(),
  ]);
  const [kpi, setKpi] = useState<StaffKpi | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    setError("");
    const opts: { from?: string; to?: string } = {};
    if (range?.[0]) opts.from = toUtcParam(range[0]);
    if (range?.[1]) opts.to = toUtcParam(range[1]);
    getKpi(token, opts)
      .then((res) => {
        const mine = staffId
          ? res.staff.find((r) => r.staff_id === staffId) ?? null
          : null;
        setKpi(mine);
      })
      .catch(() => setError("加载失败"))
      .finally(() => setLoading(false));
  }, [token, staffId, range]);

  return (
    <div className="space-y-4 p-6">
      <Flex justify="space-between" align="flex-start" wrap="wrap" gap="middle">
        <Title level={3} style={{ margin: 0 }}>
          我的 KPI
        </Title>
        <RangePicker
          value={range}
          onChange={(v) => setRange(v as [Dayjs, Dayjs] | null)}
          allowClear={false}
        />
      </Flex>

      {error && <Alert type="error" showIcon title={error} />}

      {loading ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}>
              <Skeleton active paragraph={{ rows: 1 }} />
            </Card>
          ))}
        </div>
      ) : kpi ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Card>
            <Statistic
              title="接管数"
              value={kpi.takeovers}
              prefix={<UserSwitchOutlined />}
            />
          </Card>
          <Card>
            <Statistic
              title="解决数"
              value={kpi.resolved}
              valueStyle={{
                color: kpi.resolved_ratio >= 0.7 ? "#059669" : "#dc2626",
              }}
              prefix={<CheckCircleOutlined />}
            />
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              解决率 {(kpi.resolved_ratio * 100).toFixed(0)}%
            </Typography.Text>
          </Card>
          <Card>
            <Statistic
              title="转派数"
              value={kpi.transfers ?? 0}
              valueStyle={{
                color:
                  kpi.transfer_ratio != null && kpi.transfer_ratio > 0.3
                    ? "#dc2626"
                    : undefined,
              }}
              prefix={<SwapOutlined />}
            />
            {kpi.transfer_ratio != null && (
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                转派率 {(kpi.transfer_ratio * 100).toFixed(0)}%
              </Typography.Text>
            )}
          </Card>
          <Card>
            <Statistic
              title="平均处理时长"
              value={fmtDuration(kpi.avg_handle_seconds)}
              prefix={<ClockCircleOutlined />}
            />
          </Card>
        </div>
      ) : (
        <Card>
          <Empty description="该时间段内暂无数据" />
        </Card>
      )}
    </div>
  );
}
