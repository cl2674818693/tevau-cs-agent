import { Link, useParams } from "react-router-dom";

import { getTicketDetail, type TicketDetail } from "../../api/adminTickets";
import { Alert } from "../../components/ui/alert";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "../../components/ui/breadcrumb";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { Skeleton } from "../../components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../../components/ui/tabs";
import { useAsyncData } from "../../hooks/useAsyncData";
import { useStaffSession } from "../../hooks/useStaffSession";

// ─── skeletons ─────────────────────────────────────────────────────────────────

function OverviewSkeleton() {
  return (
    <Card className="px-3 py-3">
      <div className="flex flex-col gap-2">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="flex gap-3">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-4 w-40" />
          </div>
        ))}
      </div>
    </Card>
  );
}

function EventsSkeleton() {
  return (
    <div className="flex flex-col gap-2">
      {[1, 2, 3].map((i) => (
        <Card key={i} className="px-3 py-2">
          <Skeleton className="mb-2 h-3 w-32" />
          <Skeleton className="h-4 w-full" />
        </Card>
      ))}
    </div>
  );
}

// ─── tab panels ───────────────────────────────────────────────────────────────

function OverviewTab({
  t,
  loading,
}: {
  t: TicketDetail | null;
  loading: boolean;
}) {
  if (loading) return <OverviewSkeleton />;
  if (!t) return null;

  let payload: Record<string, unknown> = {};
  try {
    payload = JSON.parse(t.payload_json) as Record<string, unknown>;
  } catch {
    payload = {};
  }

  const rows: [string, string][] = [
    ["严重度", t.current_severity ?? "—"],
    ["创建时间", t.created_at],
    ...(Object.keys(payload).length > 0
      ? (Object.entries(payload).map(([k, v]) => [k, String(v ?? "—")]) as [string, string][])
      : ([["payload", "（空）"]] as [string, string][])),
  ];

  return (
    <Card className="px-3 py-3">
      <dl className="flex flex-col gap-2 text-xs">
        {rows.map(([label, value]) => (
          <div key={label} className="flex flex-wrap gap-x-3">
            <dt className="w-24 shrink-0 text-muted-foreground">{label}</dt>
            <dd className="text-foreground">{value}</dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}

function EventsTab({
  events,
  loading,
}: {
  events: TicketDetail["events"];
  loading: boolean;
}) {
  if (loading) return <EventsSkeleton />;

  return (
    <div className="flex flex-col gap-2">
      {events.length === 0 && (
        <div className="py-4 text-center text-xs text-muted-foreground">暂无事件</div>
      )}
      {events.map((e, i) => (
        <Card key={i} className="px-3 py-2">
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
            <span className="font-medium text-foreground">{e.event}</span>
            <span className="text-[10px] text-muted-foreground">{e.created_at}</span>
          </div>
          {(e.actor || e.comment) && (
            <div className="mt-1 text-[10px] text-muted-foreground">
              {e.actor && <span>执行人：{e.actor}</span>}
              {e.actor && e.comment && <span className="mx-1">·</span>}
              {e.comment && <span>{e.comment}</span>}
            </div>
          )}
        </Card>
      ))}
    </div>
  );
}

function ConversationsTab({
  t,
  loading,
}: {
  t: TicketDetail | null;
  loading: boolean;
}) {
  if (loading) {
    return (
      <Card className="px-3 py-2">
        <Skeleton className="h-4 w-48" />
      </Card>
    );
  }
  if (!t) return null;

  return (
    <div className="flex flex-col gap-2">
      <Card className="px-3 py-2">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="text-muted-foreground">会话 ID</span>
          <Link
            className="font-medium text-primary hover:underline"
            to={`/staff/conversations/${t.conversation_id}`}
          >
            #{t.conversation_id}
          </Link>
          <Link
            className="ml-auto text-[10px] text-muted-foreground hover:text-primary"
            to={`/staff/conversations/${t.conversation_id}/logs`}
          >
            查看日志 →
          </Link>
        </div>
      </Card>
    </div>
  );
}

// ─── main route ───────────────────────────────────────────────────────────────

export function TicketDetailRoute() {
  const { externalId = "" } = useParams();
  const { token } = useStaffSession();

  const {
    data: t,
    loading,
    error,
  } = useAsyncData(
    () => (token ? getTicketDetail(token, externalId) : null),
    [token, externalId],
    "工单加载失败",
  );

  return (
    <PageContainer width="wide">
      {/* Breadcrumb */}
      <Breadcrumb className="mb-2">
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to="/staff">工作台</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to="/staff/tickets">工单</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>{externalId}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <PageHeader
        title={`工单 — ${externalId}`}
        actions={
          <Button variant="outline" size="sm" asChild>
            <Link to="/staff/tickets">返回工单列表</Link>
          </Button>
        }
      />

      {error && (
        <Alert variant="error" className="mb-3">
          {error}
        </Alert>
      )}

      <Tabs defaultValue="overview" className="mt-1">
        <TabsList className="mb-3">
          <TabsTrigger value="overview">概览</TabsTrigger>
          <TabsTrigger value="events">事件流</TabsTrigger>
          <TabsTrigger value="conversations">关联会话</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <OverviewTab t={t} loading={loading} />
        </TabsContent>

        <TabsContent value="events">
          <EventsTab events={t?.events ?? []} loading={loading} />
        </TabsContent>

        <TabsContent value="conversations">
          <ConversationsTab t={t} loading={loading} />
        </TabsContent>
      </Tabs>
    </PageContainer>
  );
}
