import { useEffect, useMemo, useState } from "react";

import {
  listToolPolicies,
  POLICY_ROLES,
  TOOL_NAMES,
  type ToolPolicy,
  upsertToolPolicies,
} from "../../api/adminToolPolicies";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { useStaffSession } from "../../hooks/useStaffSession";

type CellState = { allowed: number; unmask_allowed: number };
type MatrixState = Record<string, Record<string, CellState>>;

function emptyMatrix(): MatrixState {
  const m: MatrixState = {};
  for (const t of TOOL_NAMES) {
    m[t] = {};
    for (const r of POLICY_ROLES) m[t][r] = { allowed: 0, unmask_allowed: 0 };
  }
  return m;
}

function applyRowsToMatrix(rows: ToolPolicy[]): MatrixState {
  const m = emptyMatrix();
  for (const row of rows) {
    if (m[row.tool_name]?.[row.role]) {
      m[row.tool_name][row.role] = {
        allowed: Number(row.allowed),
        unmask_allowed: Number(row.unmask_allowed),
      };
    }
  }
  return m;
}

function flatten(m: MatrixState) {
  const out: { tool_name: string; role: string; allowed: number; unmask_allowed: number }[] = [];
  for (const t of TOOL_NAMES)
    for (const r of POLICY_ROLES) {
      out.push({ tool_name: t, role: r, ...m[t][r] });
    }
  return out;
}

function MatrixHeader() {
  return (
    <thead>
      <tr className="border-b border-line text-ink-secondary">
        <th className="px-3 py-2 text-left font-normal">工具</th>
        {POLICY_ROLES.map((r) => (
          <th key={r} className="px-3 py-2 text-center font-normal">
            {r}
            <br />
            <span className="text-footnote">允许 / 解锁</span>
          </th>
        ))}
      </tr>
    </thead>
  );
}

function MatrixRow({
  tool,
  value,
  onSet,
}: {
  tool: string;
  value: Record<string, CellState>;
  onSet: (role: string, key: keyof CellState, v: number) => void;
}) {
  return (
    <tr className="border-b border-line last:border-0">
      <td className="px-3 py-2 text-ink-primary">{tool}</td>
      {POLICY_ROLES.map((r) => (
        <td key={r} className="px-3 py-2 text-center">
          <div className="flex justify-center gap-2">
            <input type="checkbox" aria-label={`${tool}/${r}/allowed`}
              checked={value[r].allowed === 1}
              onChange={(e) => onSet(r, "allowed", e.target.checked ? 1 : 0)} />
            <input type="checkbox" aria-label={`${tool}/${r}/unmask`}
              checked={value[r].unmask_allowed === 1}
              onChange={(e) => onSet(r, "unmask_allowed", e.target.checked ? 1 : 0)} />
          </div>
        </td>
      ))}
    </tr>
  );
}

function MatrixTable({
  value,
  onChange,
}: {
  value: MatrixState;
  onChange: (next: MatrixState) => void;
}) {
  function setCell(tool: string, role: string, key: keyof CellState, v: number) {
    const next: MatrixState = { ...value, [tool]: { ...value[tool] } };
    next[tool][role] = { ...next[tool][role], [key]: v };
    onChange(next);
  }
  return (
    <Card>
      <div className="overflow-x-auto">
        <table className="w-full text-body3">
          <MatrixHeader />
          <tbody>
            {TOOL_NAMES.map((t) => (
              <MatrixRow key={t} tool={t} value={value[t]}
                onSet={(r, k, v) => setCell(t, r, k, v)} />
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

export function ToolPoliciesRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "engineer" || role === "admin";
  const [matrix, setMatrix] = useState<MatrixState>(emptyMatrix);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (!token || !allowed) {
      setErr("需要工程或管理员权限");
      setLoading(false);
      return;
    }
    setLoading(true);
    listToolPolicies(token)
      .then((rows) => setMatrix(applyRowsToMatrix(rows)))
      .catch(() => setErr("加载失败"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role]);

  const items = useMemo(() => flatten(matrix), [matrix]);

  async function save() {
    if (!token) return;
    setErr("");
    setNotice("");
    try {
      await upsertToolPolicies(token, items);
      setNotice("已保存（缓存已刷新）");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "保存失败");
    }
  }

  return (
    <PageContainer width="wide">
      <PageHeader title="AI 工具权限矩阵" />
      {err && <Alert variant="error" className="mb-2">{err}</Alert>}
      {notice && <Alert variant="success" className="mb-2">{notice}</Alert>}
      {loading ? (
        <LoadingState />
      ) : (
        allowed && (
          <>
            <MatrixTable value={matrix} onChange={setMatrix} />
            <div className="mt-3">
              <Button size="md" onClick={save}>保存</Button>
            </div>
            <p className="mt-2 text-footnote text-ink-tertiary">
              admin 角色默认全部允许，不在矩阵中显示。空表回退到 M1 默认白名单。
            </p>
          </>
        )
      )}
    </PageContainer>
  );
}
