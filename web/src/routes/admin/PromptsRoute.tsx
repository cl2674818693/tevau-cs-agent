import { useEffect, useState } from "react";

import { getPromptAbStats, getPromptVersions, setRollout } from "../../api/admin";
import type { PromptAbStat } from "../../api/admin";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
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
      <span className="flex-1 text-sm text-foreground">{version}</span>
      <Input
        type="number"
        min={0}
        max={100}
        aria-label={`${version} 灰度比例`}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-20 px-2 py-1 text-sm"
      />
      <span className="text-xs text-muted-foreground">%</span>
    </div>
  );
}

/** 将 Date 转成后端要求的 "YYYY-MM-DD HH:MM:SS" UTC 格式 */
function toUtcParam(d: Date): string {
  return d.toISOString().slice(0, 19).replace("T", " ");
}

/** 时间窗选项 */
type WindowOption = "7d" | "30d";

function windowFrom(opt: WindowOption): string {
  const now = new Date();
  const days = opt === "7d" ? 7 : 30;
  return toUtcParam(new Date(now.getTime() - days * 24 * 60 * 60 * 1000));
}

export function PromptsRoute() {
  const { token, role } = useStaffSession();
  const [versions, setVersions] = useState<string[]>([]);
  const [rollout, setRolloutState] = useState<Record<string, number>>({});
  const [notice, setNotice] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  // AB 表现
  const [window, setWindow] = useState<WindowOption>("7d");
  const [abStats, setAbStats] = useState<PromptAbStat[]>([]);
  const [abErr, setAbErr] = useState("");
  const [abLoading, setAbLoading] = useState(false);

  useEffect(() => {
    if (!token || role !== "admin") {
      setErr("需要 admin 权限");
      setLoading(false);
      return;
    }
    setLoading(true);
    getPromptVersions(token)
      .then((d) => {
        setVersions(d.versions);
        setRolloutState(d.rollout);
      })
      .catch(() => setErr("加载失败"))
      .finally(() => setLoading(false));
  }, [token, role]);

  useEffect(() => {
    if (!token || role !== "admin") return;
    setAbLoading(true);
    setAbErr("");
    getPromptAbStats(token, { from: windowFrom(window) })
      .then((d) => setAbStats(d.versions))
      .catch(() => setAbErr("加载表现数据失败"))
      .finally(() => setAbLoading(false));
  }, [token, role, window]);

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
      {loading ? (
        <LoadingState />
      ) : (
        !err && (
          <>
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
            <div className="mt-2 text-[10px] text-muted-foreground">
              合计 {total}%（≤100，余量回落 default）
            </div>
            <Button size="sm" className="mt-3" onClick={save} disabled={total > 100}>
              保存
            </Button>

            {/* 各版本表现对比 */}
            <div className="mt-6">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-foreground">各版本表现</span>
          <div className="flex gap-1">
            {(["7d", "30d"] as WindowOption[]).map((opt) => (
              <button
                key={opt}
                onClick={() => setWindow(opt)}
                className={[
                  "px-2 py-0.5 rounded text-xs transition-colors",
                  window === opt
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:text-foreground",
                ].join(" ")}
              >
                {opt === "7d" ? "近 7 天" : "近 30 天"}
              </button>
            ))}
          </div>
        </div>
        {abErr && (
          <Alert variant="error" className="mb-2">
            {abErr}
          </Alert>
        )}
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b text-muted-foreground">
                  <th className="px-3 py-2 text-left font-normal">版本</th>
                  <th className="px-3 py-2 text-right font-normal">assistant 轮次</th>
                  <th className="px-3 py-2 text-right font-normal">失败数</th>
                  <th className="px-3 py-2 text-right font-normal">失败率</th>
                  <th className="px-3 py-2 text-right font-normal">差评数</th>
                  <th className="px-3 py-2 text-right font-normal">差评率</th>
                </tr>
              </thead>
              <tbody>
                {abLoading && (
                  <tr>
                    <td colSpan={6} className="px-3 py-4 text-center text-muted-foreground">
                      加载中…
                    </td>
                  </tr>
                )}
                {!abLoading && abStats.length === 0 && !abErr && (
                  <tr>
                    <td colSpan={6} className="px-3 py-4 text-center text-muted-foreground">
                      暂无数据
                    </td>
                  </tr>
                )}
                {!abLoading &&
                  abStats.map((s) => {
                    const failedHigh = s.failed_rate > 0.1;
                    const downvoteHigh = s.downvote_rate > 0.2;
                    return (
                      <tr key={s.version} className="border-b last:border-0">
                        <td className="px-3 py-2 text-foreground">{s.version}</td>
                        <td className="px-3 py-2 text-right text-muted-foreground">
                          {s.assistant_turns}
                        </td>
                        <td
                          className={[
                            "px-3 py-2 text-right",
                            failedHigh ? "text-status-error" : "text-muted-foreground",
                          ].join(" ")}
                        >
                          {s.failed}
                        </td>
                        <td
                          className={[
                            "px-3 py-2 text-right",
                            failedHigh ? "text-status-error" : "text-muted-foreground",
                          ].join(" ")}
                        >
                          {(s.failed_rate * 100).toFixed(1)}%
                        </td>
                        <td
                          className={[
                            "px-3 py-2 text-right",
                            downvoteHigh ? "text-status-error" : "text-muted-foreground",
                          ].join(" ")}
                        >
                          {s.downvote}
                        </td>
                        <td
                          className={[
                            "px-3 py-2 text-right",
                            downvoteHigh ? "text-status-error" : "text-muted-foreground",
                          ].join(" ")}
                        >
                          {(s.downvote_rate * 100).toFixed(1)}%
                        </td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        </Card>
              <p className="mt-1 text-[10px] text-muted-foreground">
                差评率分母 = 该版本 assistant 消息数
              </p>
            </div>
          </>
        )
      )}
    </PageContainer>
  );
}
