import { useEffect, useState } from "react";
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
} from "recharts";
import { DollarSign, Cpu, TrendingUp, BarChart2 } from "lucide-react";

import {
  getUsage,
  listPricing,
  type Pricing,
  upsertPricing,
  type UsageItem,
} from "../../api/adminCost";
import { KpiCard } from "../../components/admin/KpiCard";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { DatePicker } from "../../components/ui/date-picker";
import { Input } from "../../components/ui/input";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { Skeleton } from "../../components/ui/skeleton";
import { useStaffSession } from "../../hooks/useStaffSession";

function toUtcParam(d: Date): string {
  return d.toISOString().slice(0, 19).replace("T", " ");
}

function KpiSkeleton() {
  return (
    <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <Skeleton key={i} className="h-[100px] rounded-xl" />
      ))}
    </div>
  );
}

function ChartSkeleton() {
  return <Skeleton className="h-[300px] rounded-xl" />;
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

function PricingForm({
  onSaved,
  onError,
}: {
  onSaved: () => void;
  onError: (m: string) => void;
}) {
  const { token } = useStaffSession();
  const [model, setModel] = useState("claude-sonnet-4-6");
  const [inP, setInP] = useState(30000);
  const [outP, setOutP] = useState(150000);
  const [cur, setCur] = useState("USD");
  async function submit() {
    if (!token) return;
    try {
      await upsertPricing(token, {
        model,
        input_price_per_1k_x10000: Number(inP),
        output_price_per_1k_x10000: Number(outP),
        currency: cur,
      });
      onSaved();
    } catch (e) {
      onError(e instanceof Error ? e.message : "保存失败");
    }
  }
  return (
    <Card className="mt-4">
      <div className="flex flex-wrap items-end gap-2 px-4 py-3">
        <Input
          placeholder="model"
          value={model}
          className="w-56"
          onChange={(e) => setModel(e.target.value)}
        />
        <Input
          type="number"
          value={inP}
          aria-label="输入单价×10000/千token"
          className="w-32"
          onChange={(e) => setInP(Number(e.target.value))}
        />
        <Input
          type="number"
          value={outP}
          aria-label="输出单价×10000/千token"
          className="w-32"
          onChange={(e) => setOutP(Number(e.target.value))}
        />
        <Input
          value={cur}
          aria-label="币种"
          className="w-20"
          onChange={(e) => setCur(e.target.value)}
        />
        <Button size="sm" onClick={submit}>
          保存单价
        </Button>
      </div>
      <p className="px-4 pb-3 text-xs text-muted-foreground">
        单价存"每 1000 token × 10000"避免浮点。例：sonnet 输入 $3.00/1k → 30000。
      </p>
    </Card>
  );
}

function PricingTable({ rows }: { rows: Pricing[] }) {
  if (rows.length === 0) return null;
  return (
    <Card className="mt-4">
      <p className="px-4 pt-3 text-sm font-medium">单价配置</p>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-muted-foreground">
            <th className="px-4 py-2 text-left font-normal">模型</th>
            <th className="px-4 py-2 text-right font-normal">输入×10000</th>
            <th className="px-4 py-2 text-right font-normal">输出×10000</th>
            <th className="px-4 py-2 text-left font-normal">币种</th>
            <th className="px-4 py-2 text-left font-normal">更新时间</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((p) => (
            <tr key={p.model} className="border-b border-border last:border-0">
              <td className="px-4 py-2">{p.model}</td>
              <td className="px-4 py-2 text-right">{p.input_price_per_1k_x10000}</td>
              <td className="px-4 py-2 text-right">{p.output_price_per_1k_x10000}</td>
              <td className="px-4 py-2">{p.currency}</td>
              <td className="px-4 py-2 text-muted-foreground">{p.updated_at}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

function UsageTable({ items }: { items: UsageItem[] }) {
  return (
    <Card className="mt-4">
      <p className="px-4 pt-3 text-sm font-medium">按模型明细</p>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-muted-foreground">
            <th className="px-4 py-2 text-left font-normal">模型</th>
            <th className="px-4 py-2 text-right font-normal">输入 token</th>
            <th className="px-4 py-2 text-right font-normal">输出 token</th>
            <th className="px-4 py-2 text-right font-normal">输入成本</th>
            <th className="px-4 py-2 text-right font-normal">输出成本</th>
            <th className="px-4 py-2 text-right font-normal">合计</th>
            <th className="px-4 py-2 text-left font-normal">币种</th>
          </tr>
        </thead>
        <tbody>
          {items.length === 0 && (
            <tr>
              <td colSpan={7} className="px-4 py-4 text-center text-muted-foreground">
                暂无数据
              </td>
            </tr>
          )}
          {items.map((i) => (
            <tr key={i.model} className="border-b border-border last:border-0">
              <td className="px-4 py-2">{i.model}</td>
              <td className="px-4 py-2 text-right text-muted-foreground">{i.input_tokens}</td>
              <td className="px-4 py-2 text-right text-muted-foreground">{i.output_tokens}</td>
              <td className="px-4 py-2 text-right text-muted-foreground">
                {i.input_cost?.toFixed(4) ?? "—"}
              </td>
              <td className="px-4 py-2 text-right text-muted-foreground">
                {i.output_cost?.toFixed(4) ?? "—"}
              </td>
              <td className="px-4 py-2 text-right font-medium">
                {i.total_cost?.toFixed(4) ?? "—"}
              </td>
              <td className="px-4 py-2 text-muted-foreground">{i.currency ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

export function CostRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "engineer" || role === "manager" || role === "admin";
  const canEditPricing = role === "engineer" || role === "admin";

  const defaultFrom = new Date(Date.now() - 30 * 24 * 3600 * 1000);
  const defaultTo = new Date();

  const [fromDate, setFromDate] = useState<Date | undefined>(defaultFrom);
  const [toDate, setToDate] = useState<Date | undefined>(defaultTo);
  const [items, setItems] = useState<UsageItem[]>([]);
  const [pricing, setPricing] = useState<Pricing[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [notice, setNotice] = useState("");

  function reload() {
    if (!token) return;
    setLoading(true);
    setErr("");
    const opts: Parameters<typeof getUsage>[1] = { with_cost: true };
    if (fromDate) opts.from = toUtcParam(fromDate);
    if (toDate) opts.to = toUtcParam(toDate);
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
  }, [token, role, fromDate, toDate]);

  const { totalTokens, totalCost } = buildKpi(items);
  const avgCostPerModel = items.length > 0 ? totalCost / items.length : 0;
  const currency = items[0]?.currency ?? "USD";

  const barData = items.map((i) => ({
    name: i.model,
    cost: +(i.total_cost ?? 0).toFixed(4),
    tokens: (i.input_tokens ?? 0) + (i.output_tokens ?? 0),
  }));

  return (
    <PageContainer width="wide">
      <PageHeader
        title="成本大盘"
        actions={
          <div className="flex items-center gap-2">
            <DatePicker date={fromDate} onChange={setFromDate} placeholder="开始日期" />
            <span className="text-sm text-muted-foreground">至</span>
            <DatePicker date={toDate} onChange={setToDate} placeholder="结束日期" />
          </div>
        }
      />

      {err && (
        <Alert variant="error" className="mb-4">
          {err}
        </Alert>
      )}
      {notice && (
        <Alert variant="success" className="mb-4">
          {notice}
        </Alert>
      )}

      {/* KPI 卡片 */}
      {loading ? (
        <KpiSkeleton />
      ) : allowed ? (
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
          <KpiCard
            label="总 Token 用量"
            value={totalTokens.toLocaleString()}
            icon={Cpu}
          />
          <KpiCard
            label={`API 费用（${currency}）`}
            value={totalCost.toFixed(4)}
            icon={DollarSign}
          />
          <KpiCard
            label="平均单模型成本"
            value={avgCostPerModel.toFixed(4)}
            icon={TrendingUp}
          />
          <KpiCard
            label="模型数"
            value={items.length.toString()}
            icon={BarChart2}
          />
        </div>
      ) : null}

      {/* 按模型成本柱状图 */}
      {loading && (
        <div className="mt-6">
          <ChartSkeleton />
        </div>
      )}

      {!loading && allowed && barData.length > 0 && (
        <div className="mt-6 rounded-md border border-border bg-card p-4">
          <p className="mb-3 text-sm font-medium text-muted-foreground">按模型 API 费用</p>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={barData} margin={{ top: 4, right: 16, left: 0, bottom: 40 }}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
              <XAxis
                dataKey="name"
                stroke="hsl(var(--muted-foreground))"
                tick={{ fontSize: 11 }}
                angle={-20}
                textAnchor="end"
                interval={0}
              />
              <YAxis
                stroke="hsl(var(--muted-foreground))"
                tick={{ fontSize: 12 }}
                tickFormatter={(v) => `$${v}`}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "hsl(var(--popover))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "0.5rem",
                }}
                formatter={(value) => [`$${value}`, "费用"]}
              />
              <Bar dataKey="cost" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* 按模型明细表 */}
      {!loading && allowed && <UsageTable items={items} />}

      {/* 单价配置 */}
      {!loading && allowed && (
        <>
          {canEditPricing && (
            <PricingForm
              onSaved={() => {
                setNotice("已保存");
                reload();
              }}
              onError={setErr}
            />
          )}
          <PricingTable rows={pricing} />
        </>
      )}
    </PageContainer>
  );
}
