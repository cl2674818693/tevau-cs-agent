import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { listStaffConversations, type StaffConversation } from "../../api/staff";
import { Alert } from "../../components/ui/alert";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { EmptyState } from "../../components/ui/empty-state";
import { FilterTabs } from "../../components/ui/filter-tabs";
import { PageContainer, PageHeader } from "../../components/ui/page";
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
  const [items, setItems] = useState<StaffConversation[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!token) return;
    listStaffConversations(token, status)
      .then(setItems)
      .catch(() => setErr("加载失败，请重新登录"));
  }, [token, status]);

  return (
    <PageContainer>
      <PageHeader title="客服工作台" />
      <FilterTabs className="mb-3" value={status} onChange={setStatus} options={FILTER_OPTIONS} />
      {err && (
        <Alert variant="error" className="mb-3">
          {err}
        </Alert>
      )}
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
        {items.length === 0 && !err && <EmptyState>暂无会话</EmptyState>}
      </ul>
    </PageContainer>
  );
}
