import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import {
  getStaffConversation,
  releaseConversation,
  streamStaffEvents,
  takeConversation,
  type StaffStreamEvent,
} from "../../api/staff";
import { AiDraftPanel } from "../../components/AiDraftPanel";
import { AiToolsPanel } from "../../components/AiToolsPanel";
import { TakeoverFooter } from "../../components/TakeoverFooter";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { useAiDraft } from "../../hooks/useAiDraft";
import { useStaffSession } from "../../hooks/useStaffSession";

/** 订阅会话事件总线，返回累积的事件列表 + 追加器。 */
function useStaffStream(
  token: string | null,
  convId: number,
): [StaffStreamEvent[], (e: StaffStreamEvent) => void] {
  const [events, setEvents] = useState<StaffStreamEvent[]>([]);
  const stopped = useRef(false);
  useEffect(() => {
    if (!token) return;
    stopped.current = false;
    (async () => {
      try {
        for await (const ev of streamStaffEvents(token, convId)) {
          if (stopped.current) break;
          setEvents((prev) => [...prev, ev]);
        }
      } catch {
        /* 流断开，忽略 */
      }
    })();
    return () => {
      stopped.current = true;
    };
  }, [token, convId]);
  return [events, (e) => setEvents((prev) => [...prev, e])];
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

function EventLog({ events }: { events: StaffStreamEvent[] }) {
  return (
    <ul className="mb-3 flex flex-1 flex-col gap-1 overflow-y-auto">
      {events.map((ev, i) => (
        <li key={i} className="text-body2 text-ink-primary">
          <span className="mr-1 text-footnote text-ink-secondary">[{ev.type}]</span>
          {ev.content ?? ev.to ?? ""}
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
  const [events, pushEvent] = useStaffStream(token, convId);
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
    <PageContainer fullHeight>
      <PageHeader
        title={`会话 #${convId}`}
        actions={
          <>
            <Button size="sm" variant="ghost" onClick={onToggleDraftMode}>
              {draftMode ? "关闭草稿模式" : "AI 草稿模式"}
            </Button>
            {taken ? (
              <Button size="sm" variant="ghost" onClick={onRelease}>
                释放回 AI
              </Button>
            ) : (
              <Button size="sm" onClick={onTake}>
                接管
              </Button>
            )}
          </>
        }
      />
      {notice && (
        <Alert variant="info" className="mb-2">
          {notice}
        </Alert>
      )}
      <AiDraftPanel draft={aiDraft} onApprove={approve} onReject={reject} />
      {canUseTools && token && (
        <div className="mb-3">
          <AiToolsPanel token={token} convId={convId} />
        </div>
      )}
      <EventLog events={events} />
      {taken && token && (
        <TakeoverFooter
          token={token}
          convId={convId}
          onLocalEvent={pushEvent}
          onNotice={setNotice}
          onReleased={() => setTaken(false)}
        />
      )}
    </PageContainer>
  );
}
