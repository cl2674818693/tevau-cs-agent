import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getTicketDetail, type TicketDetail } from "../../api/adminTickets";
import { Alert } from "../../components/ui/alert";
import { Card } from "../../components/ui/card";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { useStaffSession } from "../../hooks/useStaffSession";

function HeaderCard({ t, payload }: { t: TicketDetail; payload: Record<string, unknown> }) {
  return (
    <Card>
      <div className="flex flex-col gap-1 px-page py-block-sm text-body3">
        <div>严重度：{t.current_severity ?? "—"}</div>
        <div>分类：{String(payload.category ?? "—")}</div>
        <div>创建时间：{t.created_at}</div>
        <div>
          关联会话：
          <Link className="text-brand" to={`/staff/conversations/${t.conversation_id}/logs`}>
            #{t.conversation_id}
          </Link>
        </div>
      </div>
    </Card>
  );
}

function EventsList({ events }: { events: TicketDetail["events"] }) {
  return (
    <Card className="mt-2">
      <ul className="flex flex-col">
        {events.length === 0 && (
          <li className="px-page py-block-sm text-ink-tertiary">暂无事件</li>
        )}
        {events.map((e, i) => (
          <li key={i} className="border-b border-line px-page py-block-sm last:border-0">
            <div className="flex justify-between text-body3">
              <span className="text-ink-primary">{e.event}</span>
              <span className="text-ink-tertiary">{e.created_at}</span>
            </div>
            {(e.actor || e.comment) && (
              <div className="mt-0.5 text-footnote text-ink-secondary">
                {e.actor && <span>受理人：{e.actor} </span>}
                {e.comment && <span>· {e.comment}</span>}
              </div>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
}

export function TicketDetailRoute() {
  const { externalId = "" } = useParams();
  const { token } = useStaffSession();
  const [t, setT] = useState<TicketDetail | null>(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    getTicketDetail(token, externalId)
      .then(setT)
      .catch((e) => setErr(e instanceof Error ? e.message : "加载失败"))
      .finally(() => setLoading(false));
  }, [token, externalId]);

  let payload: Record<string, unknown> = {};
  if (t) {
    try { payload = JSON.parse(t.payload_json); } catch { payload = {}; }
  }

  return (
    <PageContainer width="wide">
      <PageHeader title={`工单 ${externalId}`} />
      {err && <Alert variant="error" className="mb-2">{err}</Alert>}
      {loading ? (
        <LoadingState />
      ) : (
        t && (
          <>
            <HeaderCard t={t} payload={payload} />
            <div className="mt-4 text-body2 font-medium text-ink-primary">事件链</div>
            <EventsList events={t.events} />
          </>
        )
      )}
    </PageContainer>
  );
}
