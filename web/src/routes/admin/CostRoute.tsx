import {
  BarChartOutlined,
  DollarOutlined,
  RiseOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import {
  Alert,
  App,
  Button,
  Card,
  DatePicker,
  Flex,
  Form,
  Input,
  InputNumber,
  Skeleton,
  Statistic,
  Table,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import type { Dayjs } from "dayjs";
import dayjs from "dayjs";
import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip as ReTooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  getUsage,
  listPricing,
  type Pricing,
  upsertPricing,
  type UsageItem,
} from "../../api/adminCost";
import { useStaffSession } from "../../hooks/useStaffSession";

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;

function toUtcParam(d: Dayjs): string {
  return d.toDate().toISOString().slice(0, 19).replace("T", " ");
}

function buildKpi(items: UsageItem[]) {
  let totalTokens = 0;
  let totalCost = 0;
  for (const item of items) {
    totalTokens += (item.input_tokens ?? 0) + (item.output_tokens ?? 0);
    totalCost += item.total_cost ?? 0;
  }
  return { totalTokens, totalCost };
}

function PricingForm({ onSaved }: { onSaved: () => void }) {
  const { token } = useStaffSession();
  const { message } = App.useApp();
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);

  async function submit(values: {
    model: string;
    input_price_per_1k_x10000: number;
    output_price_per_1k_x10000: number;
    currency: string;
  }) {
    if (!token) return;
    setSaving(true);
    try {
      await upsertPricing(token, values);
      message.success("已保存");
      onSaved();
    } catch (e) {
      message.error(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card title="新增/更新单价" size="small">
      <Form
        form={form}
        layout="inline"
        initialValues={{
          model: "claude-sonnet-4-6",
          input_price_per_1k_x10000: 30000,
          output_price_per_1k_x10000: 150000,
          currency: "USD",
        }}
        onFinish={submit}
      >
        <Form.Item name="model" label="模型" rules={[{ required: true }]}>
          <Input style={{ width: 200 }} />
        </Form.Item>
        <Form.Item
          name="input_price_per_1k_x10000"
          label="输入×10000"
          rules={[{ required: true, type: "number" }]}
        >
          <InputNumber min={0} style={{ width: 120 }} />
        </Form.Item>
        <Form.Item
          name="output_price_per_1k_x10000"
          label="输出×10000"
          rules={[{ required: true, type: "number" }]}
        >
          <InputNumber min={0} style={{ width: 120 }} />
        </Form.Item>
        <Form.Item name="currency" label="币种" rules={[{ required: true }]}>
          <Input style={{ width: 80 }} />
        </Form.Item>
        <Form.Item>
          <Button type="primary" htmlType="submit" loading={saving}>
            保存单价
          </Button>
        </Form.Item>
      </Form>
      <Text type="secondary" style={{ fontSize: 12 }}>
        单价存"每 1000 token × 10000"避免浮点。例：sonnet 输入 $3.00/1k → 30000。
      </Text>
    </Card>
  );
}

function KpiCards({
  loading,
  totalTokens,
  totalCost,
  avgCostPerModel,
  modelCount,
  currency,
}: {
  loading: boolean;
  totalTokens: number;
  totalCost: number;
  avgCostPerModel: number;
  modelCount: number;
  currency: string;
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
  return (
    <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
      <Card>
        <Statistic
          title="总 Token 用量"
          value={totalTokens}
          prefix={<ThunderboltOutlined />}
        />
      </Card>
      <Card>
        <Statistic
          title={`API 费用（${currency}）`}
          value={totalCost}
          precision={4}
          prefix={<DollarOutlined />}
        />
      </Card>
      <Card>
        <Statistic
          title="平均单模型成本"
          value={avgCostPerModel}
          precision={4}
          prefix={<RiseOutlined />}
        />
      </Card>
      <Card>
        <Statistic
          title="模型数"
          value={modelCount}
          prefix={<BarChartOutlined />}
        />
      </Card>
    </div>
  );
}

export function CostRoute() {
  const { token, role } = useStaffSession();
  const allowed =
    role === "engineer" || role === "manager" || role === "admin";
  const canEditPricing = role === "engineer" || role === "admin";

  const [range, setRange] = useState<[Dayjs, Dayjs] | null>([
    dayjs().subtract(30, "day"),
    dayjs(),
  ]);
  const [items, setItems] = useState<UsageItem[]>([]);
  const [pricing, setPricing] = useState<Pricing[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  function reload() {
    if (!token) return;
    setLoading(true);
    setErr("");
    const opts: Parameters<typeof getUsage>[1] = { with_cost: true };
    if (range?.[0]) opts.from = toUtcParam(range[0]);
    if (range?.[1]) opts.to = toUtcParam(range[1]);
    Promise.all([getUsage(token, opts), listPricing(token)])
      .then(([u, p]) => {
        setItems(u);
        setPricing(p);
      })
      .catch(() => setErr("加载失败"))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token || !allowed) {
      setErr("需要管理权限");
      setLoading(false);
      return;
    }
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role, range]);

  const { totalTokens, totalCost } = buildKpi(items);
  const avgCostPerModel = items.length > 0 ? totalCost / items.length : 0;
  const currency = items[0]?.currency ?? "USD";

  const barData = useMemo(
    () =>
      items.map((i) => ({
        name: i.model,
        cost: +(i.total_cost ?? 0).toFixed(4),
      })),
    [items],
  );

  const usageColumns: ColumnsType<UsageItem> = useMemo(
    () => [
      { title: "模型", dataIndex: "model" },
      {
        title: "输入 token",
        dataIndex: "input_tokens",
        align: "right",
        render: (v: number) => v?.toLocaleString() ?? "—",
      },
      {
        title: "输出 token",
        dataIndex: "output_tokens",
        align: "right",
        render: (v: number) => v?.toLocaleString() ?? "—",
      },
      {
        title: "输入成本",
        dataIndex: "input_cost",
        align: "right",
        render: (v: number) => (v != null ? v.toFixed(4) : "—"),
      },
      {
        title: "输出成本",
        dataIndex: "output_cost",
        align: "right",
        render: (v: number) => (v != null ? v.toFixed(4) : "—"),
      },
      {
        title: "合计",
        dataIndex: "total_cost",
        align: "right",
        render: (v: number) => (
          <Text strong>{v != null ? v.toFixed(4) : "—"}</Text>
        ),
      },
      { title: "币种", dataIndex: "currency", width: 80 },
    ],
    [],
  );

  const pricingColumns: ColumnsType<Pricing> = useMemo(
    () => [
      { title: "模型", dataIndex: "model" },
      {
        title: "输入×10000",
        dataIndex: "input_price_per_1k_x10000",
        align: "right",
      },
      {
        title: "输出×10000",
        dataIndex: "output_price_per_1k_x10000",
        align: "right",
      },
      { title: "币种", dataIndex: "currency", width: 80 },
      {
        title: "更新时间",
        dataIndex: "updated_at",
        render: (v: string) => (
          <Text type="secondary" style={{ fontSize: 12 }}>
            {v}
          </Text>
        ),
      },
    ],
    [],
  );

  return (
    <div className="space-y-4 p-6">
      <Flex justify="space-between" align="flex-start" wrap="wrap" gap="middle">
        <Title level={3} style={{ margin: 0 }}>
          成本大盘
        </Title>
        <RangePicker
          value={range}
          onChange={(v) => setRange(v as [Dayjs, Dayjs] | null)}
          allowClear={false}
        />
      </Flex>

      {err && <Alert type="error" showIcon title={err} />}

      {allowed && (
        <KpiCards
          loading={loading}
          totalTokens={totalTokens}
          totalCost={totalCost}
          avgCostPerModel={avgCostPerModel}
          modelCount={items.length}
          currency={currency}
        />
      )}

      {!loading && allowed && barData.length > 0 && (
        <Card title="按模型 API 费用" size="small">
          <ResponsiveContainer width="100%" height={300}>
            <BarChart
              data={barData}
              margin={{ top: 4, right: 16, left: 0, bottom: 40 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis
                dataKey="name"
                stroke="#6b7280"
                tick={{ fontSize: 11 }}
                angle={-20}
                textAnchor="end"
                interval={0}
              />
              <YAxis
                stroke="#6b7280"
                tick={{ fontSize: 12 }}
                tickFormatter={(v) => `$${v}`}
              />
              <ReTooltip
                contentStyle={{
                  backgroundColor: "#fff",
                  border: "1px solid #e5e7eb",
                  borderRadius: 8,
                }}
                formatter={(value) => [`$${value}`, "费用"]}
              />
              <Bar dataKey="cost" fill="#4f46e5" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      {!loading && allowed && (
        <Card title="按模型明细" size="small">
          <Table<UsageItem>
            rowKey="model"
            size="small"
            columns={usageColumns}
            dataSource={items}
            pagination={false}
            locale={{ emptyText: "暂无数据" }}
          />
        </Card>
      )}

      {!loading && allowed && canEditPricing && (
        <PricingForm onSaved={reload} />
      )}

      {!loading && allowed && pricing.length > 0 && (
        <Card title="单价配置" size="small">
          <Table<Pricing>
            rowKey="model"
            size="small"
            columns={pricingColumns}
            dataSource={pricing}
            pagination={false}
          />
        </Card>
      )}
    </div>
  );
}
