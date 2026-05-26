import { useState } from "react";
import { Link } from "react-router-dom";

import { listStaffConversations } from "../../api/staff";
import { Alert } from "../../components/ui/alert";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { EmptyState } from "../../components/ui/empty-state";
import { FilterTabs } from "../../components/ui/filter-tabs";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { useAsyncData } from "../../hooks/useAsyncData";
import { useStaffSession } from "../../hooks/useStaffSession";

const FILTER_OPTIONS: { value: string; label: string }[] = [
  { value: "human_pending", label: "待人工" },
  { value: "human_takeover", label: "人工接管" },
  { value: "all", label: "全部" },
];

export function ConversationsListRoute() {
  const { token, role } = useStaffSession();
  const canSpectate = role === "senior" || role === "engineer";
  const [status, setStatus] = useState<string>("human_pending");
  const { data, loading, error } = useAsyncData(
    () => (token ? listStaffConversations(token, status) : null),
    [token, status],
    "加载失败，请重新登录",
  );
  const items = data ?? [];

  return (
    <PageContainer>
      <PageHeader title="客服工作台" />
      <FilterTabs className="mb-3" value={status} onChange={setStatus} options={FILTER_OPTIONS} />
      {error && (
        <Alert variant="error" className="mb-3">
          {error}
        </Alert>
      )}
      {loading && <LoadingState />}
      <ul className="flex flex-col gap-2">
        {items.map((c) => (
          <li key={c.id} className="flex items-center gap-2">
            <Card className="flex-1 transition-colors hover:bg-surface-hover">
              <Link to={`/staff/conversations/${c.id}`} className="block px-3 py-2">
                <div className="flex items-center gap-2">
                  <span className="flex-1 text-body1 text-ink-primary">
                    #{c.id} · {c.user_type === "c" ? "C 端用户" : "BU"} {c.subject_id}
                  </span>
                  <Badge variant="neutral">{c.mode}</Badge>
                </div>
              </Link>
            </Card>
            <Button asChild variant="ghost" size="sm">
              <Link to={`/staff/conversations/${c.id}/logs`}>留痕</Link>
            </Button>
            {canSpectate && (
              <Button asChild variant="ghost" size="sm">
                <Link to={`/staff/conversations/${c.id}/spectate`}>旁观</Link>
              </Button>
            )}
          </li>
        ))}
        {items.length === 0 && !loading && !error && <EmptyState>暂无会话</EmptyState>}
      </ul>
    </PageContainer>
  );
}
