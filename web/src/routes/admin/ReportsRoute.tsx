import { useEffect, useState } from "react";

import {
  createReport, deleteReport, exportCsvUrl, listReports, type ReportDef, type ReportResult, runReport,
} from "../../api/adminReports";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { useStaffSession } from "../../hooks/useStaffSession";

const SOURCES = [
  "agent_ratings",
  "qa_reviews",
  "staff_actions",
  "daily_token_usage_by_model",
  "tool_audits",
];

function ReportForm({ onCreated, onError }: {
  onCreated: () => void; onError: (m: string) => void;
}) {
  const { token } = useStaffSession();
  const [name, setName] = useState("");
  const [source, setSource] = useState("agent_ratings");
  const [dimsRaw, setDimsRaw] = useState('["staff_id"]');
  const [metricsRaw, setMetricsRaw] = useState('[{"op":"count","col":"*","alias":"n"}]');
  async function submit() {
    if (!token || !name) return;
    let dims: string[];
    let metrics: { op: string; col: string; alias: string }[];
    try {
      dims = JSON.parse(dimsRaw);
      metrics = JSON.parse(metricsRaw);
    } catch { onError("dims/metrics JSON 格式错"); return; }
    try {
      await createReport(token, { name, source, dims, filters: [], metrics });
      setName("");
      onCreated();
    } catch (e) { onError(e instanceof Error ? e.message : "创建失败"); }
  }
  return (
    <Card>
      <div className="flex flex-col gap-2 px-page py-block-sm">
        <div className="flex flex-wrap items-end gap-2">
          <Input placeholder="报表名称" value={name} className="w-60"
            onChange={(e) => setName(e.target.value)} />
          <select value={source} onChange={(e) => setSource(e.target.value)}
            className="rounded border border-line px-2 py-1 text-body2">
            {SOURCES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <Button size="md" onClick={submit} disabled={!name}>新建报表</Button>
        </div>
        <span className="text-footnote text-ink-tertiary">
          dims：列名数组（例 <code>{`["staff_id"]`}</code>）
        </span>
        <textarea className="rounded border border-line px-2 py-1 font-mono text-body3"
          rows={2} value={dimsRaw} aria-label="dims JSON"
          onChange={(e) => setDimsRaw(e.target.value)} />
        <span className="text-footnote text-ink-tertiary">
          metrics：op ∈ count/sum/avg/min/max/count_if；count_if 需带 <code>match</code> 值
        </span>
        <textarea className="rounded border border-line px-2 py-1 font-mono text-body3"
          rows={2} value={metricsRaw} aria-label="metrics JSON"
          onChange={(e) => setMetricsRaw(e.target.value)} />
      </div>
    </Card>
  );
}

function ResultPanel({ result }: { result: ReportResult | null }) {
  if (!result) return null;
  const cols = result.rows[0] ? Object.keys(result.rows[0]) : [];
  return (
    <Card className="mt-3">
      <div className="overflow-x-auto">
        <table className="w-full text-body3">
          <thead>
            <tr className="border-b border-line text-ink-secondary">
              {cols.map((c) => (
                <th key={c} className="px-3 py-2 text-left font-normal">{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {result.rows.length === 0 && (
              <tr><td colSpan={Math.max(cols.length, 1)} className="px-3 py-4 text-center text-ink-tertiary">无结果</td></tr>
            )}
            {result.rows.map((row, i) => (
              <tr key={i} className="border-b border-line last:border-0">
                {cols.map((c) => (
                  <td key={c} className="px-3 py-2 text-ink-primary">{String(row[c] ?? "")}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="px-page py-block-sm text-footnote text-ink-tertiary font-mono">SQL: {result.sql}</p>
    </Card>
  );
}

function ReportRow({ d, onChanged, onError, onResult }: {
  d: ReportDef; onChanged: () => void;
  onError: (m: string) => void; onResult: (r: ReportResult) => void;
}) {
  const { token } = useStaffSession();
  async function run() {
    if (!token) return;
    try { onResult(await runReport(token, d.id)); }
    catch (e) { onError(e instanceof Error ? e.message : "执行失败"); }
  }
  async function rm() {
    if (!token) return;
    try { await deleteReport(token, d.id); onChanged(); }
    catch (e) { onError(e instanceof Error ? e.message : "删除失败"); }
  }
  return (
    <tr className="border-b border-line last:border-0">
      <td className="px-3 py-2">{d.id}</td>
      <td className="px-3 py-2 text-ink-primary">{d.name}</td>
      <td className="px-3 py-2">{d.source}</td>
      <td className="px-3 py-2 text-ink-tertiary">{d.owner ?? "—"}</td>
      <td className="px-3 py-2">
        <div className="flex gap-2">
          <button className="text-brand" onClick={run}>运行</button>
          <a className="text-brand" href={exportCsvUrl(d.id)} target="_blank" rel="noreferrer">CSV</a>
          <button className="text-status-error" onClick={rm}>删除</button>
        </div>
      </td>
    </tr>
  );
}

function ReportsTable({ reports: rs, onChanged, onError, onResult }: {
  reports: ReportDef[]; onChanged: () => void;
  onError: (m: string) => void; onResult: (r: ReportResult) => void;
}) {
  return (
    <Card className="mt-3">
      <table className="w-full text-body3">
        <thead>
          <tr className="border-b border-line text-ink-secondary">
            <th className="px-3 py-2 text-left font-normal">ID</th>
            <th className="px-3 py-2 text-left font-normal">名称</th>
            <th className="px-3 py-2 text-left font-normal">数据源</th>
            <th className="px-3 py-2 text-left font-normal">owner</th>
            <th className="px-3 py-2 text-left font-normal">操作</th>
          </tr>
        </thead>
        <tbody>
          {rs.length === 0 && (
            <tr><td colSpan={5} className="px-3 py-4 text-center text-ink-tertiary">无报表</td></tr>
          )}
          {rs.map((d) => (
            <ReportRow key={d.id} d={d} onChanged={onChanged} onError={onError} onResult={onResult} />
          ))}
        </tbody>
      </table>
    </Card>
  );
}

export function ReportsRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "supervisor" || role === "manager" || role === "admin";
  const [reports, setReports] = useState<ReportDef[]>([]);
  const [result, setResult] = useState<ReportResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  function reload() {
    if (!token) return;
    setLoading(true);
    listReports(token).then(setReports).catch(() => setErr("加载失败")).finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token || !allowed) { setErr("需要主管/管理层/管理员权限"); setLoading(false); return; }
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role]);

  return (
    <PageContainer width="wide">
      <PageHeader title="自定义报表" />
      {err && <Alert variant="error" className="mb-2">{err}</Alert>}
      {allowed && <ReportForm onCreated={reload} onError={setErr} />}
      {loading ? <LoadingState /> : allowed && (
        <ReportsTable reports={reports} onChanged={reload} onError={setErr} onResult={setResult} />
      )}
      {result && <ResultPanel result={result} />}
    </PageContainer>
  );
}
