import { useEffect, useState } from "react";

import { listAudit, type AuditEntry } from "../../api/adminAudit";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { useStaffSession } from "../../hooks/useStaffSession";

function FilterBar({
  value,
  onChange,
  onSearch,
}: {
  value: { actor: string; action: string };
  onChange: (v: { actor: string; action: string }) => void;
  onSearch: () => void;
}) {
  return (
    <Card className="mb-3">
      <div className="flex flex-wrap items-end gap-2 px-page py-block-sm">
        <Input
          placeholder="操作人 staff_id"
          value={value.actor}
          onChange={(e) => onChange({ ...value, actor: e.target.value })}
          className="w-40"
        />
        <Input
          placeholder="动作 如 staff.create"
          value={value.action}
          onChange={(e) => onChange({ ...value, action: e.target.value })}
          className="w-44"
        />
        <Button size="md" onClick={onSearch}>
          筛选
        </Button>
      </div>
    </Card>
  );
}

function EntriesTable({ rows }: { rows: AuditEntry[] }) {
  return (
    <Card>
      <div className="overflow-x-auto">
        <table className="w-full text-body3">
          <thead>
            <tr className="border-b border-line text-ink-secondary">
              <th className="px-3 py-2 text-left font-normal">时间</th>
              <th className="px-3 py-2 text-left font-normal">操作人</th>
              <th className="px-3 py-2 text-left font-normal">动作</th>
              <th className="px-3 py-2 text-left font-normal">对象</th>
              <th className="px-3 py-2 text-left font-normal">详情</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={5} className="px-3 py-4 text-center text-ink-tertiary">
                  暂无记录
                </td>
              </tr>
            )}
            {rows.map((e) => (
              <tr key={e.id} className="border-b border-line last:border-0">
                <td className="px-3 py-2 text-ink-tertiary">{e.created_at}</td>
                <td className="px-3 py-2 text-ink-primary">{e.actor}</td>
                <td className="px-3 py-2 text-ink-secondary">{e.action}</td>
                <td className="px-3 py-2 text-ink-secondary">
                  {e.target_type ? `${e.target_type}:${e.target_id ?? ""}` : "—"}
                </td>
                <td className="px-3 py-2 text-ink-tertiary">{e.detail_json ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

export function AuditCenterRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "engineer" || role === "admin";
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [filter, setFilter] = useState({ actor: "", action: "" });

  function reload() {
    if (!token) return;
    setLoading(true);
    listAudit(token, {
      actor: filter.actor || undefined,
      action: filter.action || undefined,
    })
      .then(setEntries)
      .catch(() => setErr("加载失败"))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token || !allowed) {
      setErr("需要工程或管理员权限");
      setLoading(false);
      return;
    }
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role]);

  return (
    <PageContainer width="wide">
      <PageHeader title="操作审计" />
      {err && (
        <Alert variant="error" className="mb-2">
          {err}
        </Alert>
      )}
      {allowed && (
        <FilterBar value={filter} onChange={setFilter} onSearch={reload} />
      )}
      {loading ? <LoadingState /> : allowed && <EntriesTable rows={entries} />}
    </PageContainer>
  );
}
