import { useEffect, useState } from "react";

import {
  getUsage,
  listPricing,
  type Pricing,
  upsertPricing,
  type UsageItem,
} from "../../api/adminCost";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { useStaffSession } from "../../hooks/useStaffSession";

function UsageTable({ items }: { items: UsageItem[] }) {
  return (
    <Card>
      <table className="w-full text-body3">
        <thead>
          <tr className="border-b border-line text-ink-secondary">
            <th className="px-3 py-2 text-left font-normal">模型</th>
            <th className="px-3 py-2 text-right font-normal">输入 token</th>
            <th className="px-3 py-2 text-right font-normal">输出 token</th>
            <th className="px-3 py-2 text-right font-normal">输入成本</th>
            <th className="px-3 py-2 text-right font-normal">输出成本</th>
            <th className="px-3 py-2 text-right font-normal">合计</th>
            <th className="px-3 py-2 text-left font-normal">币种</th>
          </tr>
        </thead>
        <tbody>
          {items.length === 0 && (
            <tr>
              <td colSpan={7} className="px-3 py-4 text-center text-ink-tertiary">暂无数据</td>
            </tr>
          )}
          {items.map((i) => (
            <tr key={i.model} className="border-b border-line last:border-0">
              <td className="px-3 py-2 text-ink-primary">{i.model}</td>
              <td className="px-3 py-2 text-right text-ink-secondary">{i.input_tokens}</td>
              <td className="px-3 py-2 text-right text-ink-secondary">{i.output_tokens}</td>
              <td className="px-3 py-2 text-right text-ink-secondary">{i.input_cost?.toFixed(2) ?? "—"}</td>
              <td className="px-3 py-2 text-right text-ink-secondary">{i.output_cost?.toFixed(2) ?? "—"}</td>
              <td className="px-3 py-2 text-right text-ink-primary">{i.total_cost?.toFixed(2) ?? "—"}</td>
              <td className="px-3 py-2 text-ink-tertiary">{i.currency ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
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
    <Card className="mt-3">
      <div className="flex flex-wrap items-end gap-2 px-page py-block-sm">
        <Input placeholder="model" value={model} className="w-56"
          onChange={(e) => setModel(e.target.value)} />
        <Input type="number" value={inP} aria-label="输入单价×10000/千token" className="w-32"
          onChange={(e) => setInP(Number(e.target.value))} />
        <Input type="number" value={outP} aria-label="输出单价×10000/千token" className="w-32"
          onChange={(e) => setOutP(Number(e.target.value))} />
        <Input value={cur} aria-label="币种" className="w-20"
          onChange={(e) => setCur(e.target.value)} />
        <Button size="md" onClick={submit}>保存单价</Button>
      </div>
      <p className="px-page pb-block-sm text-footnote text-ink-tertiary">
        单价存"每 1000 token × 10000"避免浮点。例：sonnet 输入 $3.00/1k → 30000。
      </p>
    </Card>
  );
}

function PricingList({ rows }: { rows: Pricing[] }) {
  return (
    <Card className="mt-3">
      <table className="w-full text-body3">
        <thead>
          <tr className="border-b border-line text-ink-secondary">
            <th className="px-3 py-2 text-left font-normal">模型</th>
            <th className="px-3 py-2 text-right font-normal">输入×10000</th>
            <th className="px-3 py-2 text-right font-normal">输出×10000</th>
            <th className="px-3 py-2 text-left font-normal">币种</th>
            <th className="px-3 py-2 text-left font-normal">更新时间</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((p) => (
            <tr key={p.model} className="border-b border-line last:border-0">
              <td className="px-3 py-2 text-ink-primary">{p.model}</td>
              <td className="px-3 py-2 text-right">{p.input_price_per_1k_x10000}</td>
              <td className="px-3 py-2 text-right">{p.output_price_per_1k_x10000}</td>
              <td className="px-3 py-2">{p.currency}</td>
              <td className="px-3 py-2 text-ink-tertiary">{p.updated_at}</td>
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
  const [items, setItems] = useState<UsageItem[]>([]);
  const [pricing, setPricing] = useState<Pricing[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [notice, setNotice] = useState("");

  function reload() {
    if (!token) return;
    setLoading(true);
    Promise.all([getUsage(token, { with_cost: true }), listPricing(token)])
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
  }, [token, role]);

  return (
    <PageContainer width="wide">
      <PageHeader title="Token 成本大盘" />
      {err && <Alert variant="error" className="mb-2">{err}</Alert>}
      {notice && <Alert variant="success" className="mb-2">{notice}</Alert>}
      {loading ? (
        <LoadingState />
      ) : (
        allowed && (
          <>
            <UsageTable items={items} />
            {canEditPricing && (
              <PricingForm onSaved={() => { setNotice("已保存"); reload(); }} onError={setErr} />
            )}
            <PricingList rows={pricing} />
          </>
        )
      )}
    </PageContainer>
  );
}
