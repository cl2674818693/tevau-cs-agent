import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { staffAttachmentUrl } from "../../api/attachments";
import {
  getStaffConversation,
  releaseConversation,
  streamStaffEvents,
  takeConversation,
  type StaffStreamEvent,
} from "../../api/staff";
import { AiDraftPanel } from "../../components/AiDraftPanel";
import { ImageThumb } from "../../components/ImageThumb";
import { AiToolsPanel } from "../../components/AiToolsPanel";
import { TakeoverFooter } from "../../components/TakeoverFooter";
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
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { useAiDraft } from "../../hooks/useAiDraft";
import { useStaffSession } from "../../hooks/useStaffSession";

/**
 * 订阅会话事件总线，返回累积的事件列表。
 * stopped 必须是 effect 闭包内的局部变量，不能用 useRef：StrictMode 下 effect 会
 * mount→unmount→mount，两次 mount 共享同一个 ref，第二次 mount 会把 stopped 重置成
 * false，导致第一个订阅的 for-await 永不 break → 双订阅 → 每个事件被 push 两次。
 */
function useStaffStream(token: string | null, convId: number): StaffStreamEvent[] {
  const [events, setEvents] = useState<StaffStreamEvent[]>([]);
  useEffect(() => {
    if (!token) return;
    let stopped = false;
    (async () => {
      try {
        for await (const ev of streamStaffEvents(token, convId)) {
          if (stopped) break;
          setEvents((prev) => [...prev, ev]);
        }
      } catch {
        /* 流断开，忽略 */
      }
    })();
    return () => {
      stopped = true;
    };
  }, [token, convId]);
  return events;
}

/** 按会话真实状态初始化接管态：本客服已接管 → 直接渲染回复区，刷新后不丢。 */
function useInitialTaken(
  token: string | null,
  staffId: string | null,
  convId: number,
  setTaken: (b: boolean) => void,
): void {
  useEffect(() => {
    if (!token || !staffId) return;
    let cancelled = false;
    getStaffConversation(token, convId)
      .then((c) => {
        if (!cancelled) setTaken(c.mode === "human_takeover" && c.assigned_staff_id === staffId);
      })
      .catch(() => {
        /* 取不到状态时保持未接管 */
      });
    return () => {
      cancelled = true;
    };
  }, [token, staffId, convId, setTaken]);
}

function EventLog({ events, convId }: { events: StaffStreamEvent[]; convId: number }) {
  return (
    <ul className="flex flex-1 flex-col gap-1.5 overflow-y-auto">
      {events.map((ev, i) => (
        <li key={i} className="text-sm text-foreground leading-relaxed">
          <span className="mr-1.5 text-xs font-mono text-muted-foreground">[{ev.type}]</span>
          {ev.content ?? ev.to ?? ""}
          {ev.attachments?.length ? (
            <div className="mt-1 flex flex-wrap gap-2">
              {ev.attachments.map((a) => (
                <ImageThumb key={a.id} src={staffAttachmentUrl(convId, a.id)} />
              ))}
            </div>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

export function ConversationDetailRoute() {
  const { id } = useParams();
  const convId = Number(id);
  const { token, role, staffId } = useStaffSession();
  const canUseTools = role === "senior" || role === "engineer";
  const events = useStaffStream(token, convId);
  const [taken, setTaken] = useState(false);
  const [notice, setNotice] = useState("");
  const { draftMode, aiDraft, toggleDraftMode, approve, reject } = useAiDraft(
    token,
    convId,
    events,
    setNotice,
  );

  useInitialTaken(token, staffId, convId, setTaken);

  async function onToggleDraftMode() {
    const msg = await toggleDraftMode();
    if (msg) setNotice(msg);
  }

  async function onTake() {
    if (!token) return;
    const ok = await takeConversation(token, convId);
    setTaken(ok);
    setNotice(ok ? "已接管" : "该会话已被其他客服接管");
  }

  async function onRelease() {
    if (!token) return;
    try {
      await releaseConversation(token, convId);
      setTaken(false);
      setNotice("已释放回 AI");
    } catch {
      setNotice("释放失败，请重试");
    }
  }

  return (
    <div className="flex h-full flex-col gap-4 px-4 py-5 md:px-8 md:py-6">
      {/* Breadcrumb */}
      <div className="flex items-center justify-between gap-4">
        <Breadcrumb>
          <BreadcrumbList>
            <BreadcrumbItem>
              <BreadcrumbLink asChild>
                <Link to="/staff/conversations">会话列表</Link>
              </BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              <BreadcrumbPage>会话 #{convId}</BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>

        {/* Header actions */}
        <div className="flex shrink-0 items-center gap-2">
          <Button size="sm" variant="outline" onClick={onToggleDraftMode}>
            {draftMode ? "关闭草稿模式" : "AI 草稿模式"}
          </Button>
          {taken ? (
            <Button size="sm" variant="outline" onClick={onRelease}>
              释放回 AI
            </Button>
          ) : (
            <Button size="sm" onClick={onTake}>
              接管
            </Button>
          )}
        </div>
      </div>

      {/* Notice banner */}
      {notice && (
        <Alert variant="info" className="py-2 text-sm">
          {notice}
        </Alert>
      )}

      {/* Two-column layout: left = event stream, right = panels */}
      <div className="flex min-h-0 flex-1 gap-4">
        {/* Left: event log + takeover footer */}
        <Card className="flex min-h-0 flex-1 flex-col">
          <CardHeader className="shrink-0 border-b border-border px-4 py-3">
            <CardTitle className="text-sm font-semibold text-foreground">事件流</CardTitle>
          </CardHeader>
          <CardContent className="flex min-h-0 flex-1 flex-col gap-3 overflow-hidden p-4">
            <EventLog events={events} convId={convId} />
            {taken && token && (
              <div className="shrink-0 border-t border-border pt-3">
                <TakeoverFooter
                  token={token}
                  convId={convId}
                  onNotice={setNotice}
                  onReleased={() => setTaken(false)}
                />
              </div>
            )}
          </CardContent>
        </Card>

        {/* Right: AI draft + AI tools panels */}
        <div className="flex w-80 shrink-0 flex-col gap-4">
          <AiDraftPanel draft={aiDraft} onApprove={approve} onReject={reject} />
          {canUseTools && token && <AiToolsPanel token={token} convId={convId} />}
        </div>
      </div>
    </div>
  );
}
