import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import {
  createScorecard,
  listReviews,
  listScorecards,
  type QaReview,
  type Scorecard,
  type ScorecardItem,
  submitReview,
} from "../../api/adminQa";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { useStaffSession } from "../../hooks/useStaffSession";

function ScorecardCreator({
  onCreated,
  onError,
}: {
  onCreated: () => void;
  onError: (m: string) => void;
}) {
  const { token } = useStaffSession();
  const [name, setName] = useState("");
  const [raw, setRaw] = useState('[{"key":"polite","label":"礼貌用语"}]');
  async function submit() {
    if (!token || !name) return;
    let items: ScorecardItem[];
    try {
      items = JSON.parse(raw);
    } catch {
      onError("评分项 JSON 格式错");
      return;
    }
    try {
      await createScorecard(token, { name, items });
      setName("");
      onCreated();
    } catch (e) {
      onError(e instanceof Error ? e.message : "创建失败");
    }
  }
  return (
    <Card>
      <div className="flex flex-col gap-2 px-page py-block-sm">
        <Input placeholder="评分卡名称" value={name} onChange={(e) => setName(e.target.value)} />
        <textarea
          className="rounded border border-line px-2 py-1 font-mono text-body3"
          rows={3}
          value={raw}
          onChange={(e) => setRaw(e.target.value)}
          aria-label="评分项 JSON"
        />
        <div>
          <Button size="md" onClick={submit} disabled={!name}>
            新建评分卡
          </Button>
        </div>
      </div>
    </Card>
  );
}

function ReviewForm({
  scorecards,
  defaultConvId,
  onSubmitted,
  onError,
}: {
  scorecards: Scorecard[];
  defaultConvId: number;
  onSubmitted: () => void;
  onError: (m: string) => void;
}) {
  const { token } = useStaffSession();
  const [convId, setConvId] = useState(defaultConvId);
  const [scid, setScid] = useState(scorecards[0]?.id ?? 0);
  const [score, setScore] = useState(80);
  const [tags, setTags] = useState("");
  const [comment, setComment] = useState("");
  async function submit() {
    if (!token || !scid) return;
    try {
      await submitReview(token, {
        conversation_id: convId,
        scorecard_id: scid,
        score,
        items_result: {},
        tags: tags || undefined,
        comment: comment || undefined,
      });
      onSubmitted();
    } catch (e) {
      onError(e instanceof Error ? e.message : "提交失败");
    }
  }
  return (
    <Card className="mt-3">
      <div className="flex flex-wrap items-end gap-2 px-page py-block-sm">
        <Input type="number" min={1} value={convId} aria-label="会话 ID" className="w-28"
          onChange={(e) => setConvId(Number(e.target.value))} />
        <select value={scid} onChange={(e) => setScid(Number(e.target.value))}
          className="rounded border border-line px-2 py-1 text-body2">
          {scorecards.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        <Input type="number" min={0} max={100} value={score} aria-label="得分" className="w-20"
          onChange={(e) => setScore(Number(e.target.value))} />
        <Input placeholder="标签 excellent/violation/..." value={tags} className="w-44"
          onChange={(e) => setTags(e.target.value)} />
        <Input placeholder="备注" value={comment} className="w-60"
          onChange={(e) => setComment(e.target.value)} />
        <Button size="md" onClick={submit} disabled={!scid}>提交质检</Button>
      </div>
    </Card>
  );
}

function ReviewsList({ rows }: { rows: QaReview[] }) {
  return (
    <Card className="mt-3">
      <table className="w-full text-body3">
        <thead>
          <tr className="border-b border-line text-ink-secondary">
            <th className="px-3 py-2 text-left font-normal">时间</th>
            <th className="px-3 py-2 text-left font-normal">会话</th>
            <th className="px-3 py-2 text-left font-normal">质检员</th>
            <th className="px-3 py-2 text-right font-normal">得分</th>
            <th className="px-3 py-2 text-left font-normal">标签</th>
            <th className="px-3 py-2 text-left font-normal">备注</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td colSpan={6} className="px-3 py-4 text-center text-ink-tertiary">
                暂无记录
              </td>
            </tr>
          )}
          {rows.map((r) => (
            <tr key={r.id} className="border-b border-line last:border-0">
              <td className="px-3 py-2 text-ink-tertiary">{r.created_at}</td>
              <td className="px-3 py-2 text-ink-primary">#{r.conversation_id}</td>
              <td className="px-3 py-2 text-ink-secondary">{r.reviewer_staff_id}</td>
              <td className="px-3 py-2 text-right text-ink-primary">{r.score}</td>
              <td className="px-3 py-2 text-ink-secondary">{r.tags ?? "—"}</td>
              <td className="px-3 py-2 text-ink-tertiary">{r.comment ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

export function QaReviewRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "supervisor" || role === "admin";
  const [search] = useSearchParams();
  const defaultConvId = Number(search.get("conversation_id") ?? 0);
  const [scorecards, setScorecards] = useState<Scorecard[]>([]);
  const [reviews, setReviews] = useState<QaReview[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  function reload() {
    if (!token) return;
    setLoading(true);
    Promise.all([
      listScorecards(token, true),
      listReviews(token, defaultConvId ? { conversation_id: defaultConvId } : undefined),
    ])
      .then(([sc, rv]) => {
        setScorecards(sc);
        setReviews(rv);
      })
      .catch(() => setErr("加载失败"))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token || !allowed) {
      setErr("需要主管或管理员权限");
      setLoading(false);
      return;
    }
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role]);

  return (
    <PageContainer width="wide">
      <PageHeader title="会话质检" />
      {err && (
        <Alert variant="error" className="mb-2">
          {err}
        </Alert>
      )}
      {loading ? (
        <LoadingState />
      ) : (
        allowed && (
          <>
            <ScorecardCreator onCreated={reload} onError={setErr} />
            <ReviewForm
              scorecards={scorecards}
              defaultConvId={defaultConvId || 1}
              onSubmitted={reload}
              onError={setErr}
            />
            <ReviewsList rows={reviews} />
          </>
        )
      )}
    </PageContainer>
  );
}
