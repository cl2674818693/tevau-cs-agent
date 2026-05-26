import { getKnowledgeGaps, type KnowledgeGaps } from "../../api/staff";
import { Alert } from "../../components/ui/alert";
import { Card } from "../../components/ui/card";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { useAsyncData } from "../../hooks/useAsyncData";
import { useStaffSession } from "../../hooks/useStaffSession";

const CARDS: { key: keyof KnowledgeGaps; label: string; hint: string }[] = [
  { key: "out_of_scope", label: "范围外", hint: "话题分类判为 no（AI 答不了/超范围）" },
  { key: "failed_turns", label: "失败回合", hint: "LLM/工具失败或僵尸超时被标 failed" },
  { key: "thumbs_down", label: "差评 👎", hint: "用户对 AI 回复点踩" },
];

export function InsightsRoute() {
  const { token } = useStaffSession();
  const { data: gaps, loading, error } = useAsyncData(
    () => (token ? getKnowledgeGaps(token) : null),
    [token],
  );

  return (
    <PageContainer>
      <PageHeader title="知识缺口报表" />
      {error && (
        <Alert variant="error" className="mb-3">
          {error}
        </Alert>
      )}
      {loading ? (
        <LoadingState />
      ) : (
        <div className="grid grid-cols-3 gap-3">
          {CARDS.map((c) => (
            <Card key={c.key} className="px-3 py-4">
              <div className="text-sh1 text-ink-primary">{gaps ? gaps[c.key] : "-"}</div>
              <div className="mt-1 text-body2 text-ink-primary">{c.label}</div>
              <div className="mt-1 text-footnote text-ink-secondary">{c.hint}</div>
            </Card>
          ))}
        </div>
      )}
      <p className="mt-4 text-footnote text-ink-secondary">
        口径：全部历史。明细可在「工具审计」或具体会话的留痕页查看。
      </p>
    </PageContainer>
  );
}
