import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import {
  releaseConversation,
  streamStaffEvents,
  takeConversation,
  type StaffStreamEvent,
} from "../../api/staff";
import { AiDraftPanel } from "../../components/AiDraftPanel";
import { AiToolsPanel } from "../../components/AiToolsPanel";
import { TakeoverFooter } from "../../components/TakeoverFooter";
import { Button } from "../../components/ui/button";
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

function EventLog({ events }: { events: StaffStreamEvent[] }) {
  return (
    <ul className="flex-1 overflow-y-auto flex flex-col gap-1 mb-3">
      {events.map((ev, i) => (
        <li key={i} className="text-body2 text-ink-primary">
          <span className="text-footnote text-ink-secondary mr-1">[{ev.type}]</span>
          {ev.content ?? ev.to ?? ""}
        </li>
      ))}
    </ul>
  );
}

export function ConversationDetailRoute() {
  const { id } = useParams();
  const convId = Number(id);
  const { token, role } = useStaffSession();
  const canUseTools = role === "senior" || role === "engineer";
  const nav = useNavigate();
  const [events, pushEvent] = useStaffStream(token, convId);
  const [taken, setTaken] = useState(false);
  const [notice, setNotice] = useState("");
  const { draftMode, aiDraft, toggleDraftMode, approve, reject } = useAiDraft(
    token,
    convId,
    events,
  );

  useEffect(() => {
    if (!token) nav("/staff/login");
  }, [token, nav]);

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
    await releaseConversation(token, convId);
    setTaken(false);
    setNotice("已释放回 AI");
  }

  return (
    <div className="mx-auto flex h-full max-w-[720px] flex-col px-page py-block-lg">
      <div className="flex items-center gap-2 mb-3">
        <h2 className="text-sh2 text-ink-primary flex-1">会话 #{convId}</h2>
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
      </div>
      {notice && <div className="text-body3 text-ink-secondary mb-2">{notice}</div>}
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
        />
      )}
    </div>
  );
}
