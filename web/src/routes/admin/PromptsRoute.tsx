import { useEffect, useState } from "react";

import { getPromptVersions, setRollout } from "../../api/admin";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { useStaffSession } from "../../hooks/useStaffSession";

function RolloutRow({
  version,
  value,
  onChange,
}: {
  version: string;
  value: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="flex items-center gap-3">
      <span className="flex-1 text-body2 text-ink-primary">{version}</span>
      <Input
        type="number"
        min={0}
        max={100}
        aria-label={`${version} 灰度比例`}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-20 px-2 py-1 text-body2"
      />
      <span className="text-body3 text-ink-secondary">%</span>
    </div>
  );
}

export function PromptsRoute() {
  const { token, role } = useStaffSession();
  const [versions, setVersions] = useState<string[]>([]);
  const [rollout, setRolloutState] = useState<Record<string, number>>({});
  const [notice, setNotice] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!token || role !== "admin") {
      setErr("需要 admin 权限");
      return;
    }
    getPromptVersions(token)
      .then((d) => {
        setVersions(d.versions);
        setRolloutState(d.rollout);
      })
      .catch(() => setErr("加载失败"));
  }, [token, role]);

  const total = Object.values(rollout).reduce((a, b) => a + (b || 0), 0);

  async function save() {
    if (!token) return;
    setErr("");
    setNotice("");
    try {
      const next = await setRollout(token, rollout);
      setRolloutState(next);
      setNotice("已保存并热加载");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "保存失败");
    }
  }

  return (
    <PageContainer width="form">
      <PageHeader title="Prompt 灰度管理" />
      {err && (
        <Alert variant="error" className="mb-2">
          {err}
        </Alert>
      )}
      {notice && (
        <Alert variant="success" className="mb-2">
          {notice}
        </Alert>
      )}
      <Card>
        <div className="flex flex-col gap-2 px-page py-block-sm">
          {versions.map((v) => (
            <RolloutRow
              key={v}
              version={v}
              value={rollout[v] ?? 0}
              onChange={(n) => setRolloutState((prev) => ({ ...prev, [v]: n }))}
            />
          ))}
        </div>
      </Card>
      <div className="mt-2 text-footnote text-ink-secondary">
        合计 {total}%（≤100，余量回落 default）
      </div>
      <Button size="md" className="mt-3" onClick={save} disabled={total > 100}>
        保存
      </Button>
    </PageContainer>
  );
}
