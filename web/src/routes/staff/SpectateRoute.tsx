import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { staffAttachmentUrl } from "../../api/attachments";
import { streamSpectateEvents, type StaffStreamEvent } from "../../api/staff";
import { ImageThumb } from "../../components/ImageThumb";
import { Alert } from "../../components/ui/alert";
import { EmptyState } from "../../components/ui/empty-state";
import { PageContainer } from "../../components/ui/page";
import { useStaffSession } from "../../hooks/useStaffSession";

// 旁观流事件 → 可读文案。后端旁观流发的是 tool_use（带 name/input），不是 tool_call/content。
const LABELERS: Record<string, (ev: StaffStreamEvent) => string> = {
  assistant_text: (ev) => `AI：${ev.content ?? ""}`,
  user_message: (ev) => `用户：${ev.content ?? ""}`,
  human_message: (ev) => `客服：${ev.content ?? ""}`,
  tool_use: (ev) => `调用工具：${ev.name ?? ""}${ev.input ? ` ${JSON.stringify(ev.input)}` : ""}`,
  tool_result: (ev) => {
    if (ev.ok === false) return `工具返回：${ev.name ?? ""}（失败）`;
    const count = ev.result_count ?? 0;
    return `工具返回：${ev.name ?? ""}（${count} 条${ev.empty ? "，空" : ""}）`;
  },
  mode_change: (ev) => `模式切换 → ${ev.to ?? ""}`,
};

function label(ev: StaffStreamEvent): string {
  return LABELERS[ev.type]?.(ev) ?? `[${ev.type}] ${ev.content ?? ""}`;
}

export function SpectateRoute() {
  const { id } = useParams();
  const convId = Number(id);
  const { token, role } = useStaffSession();
  const nav = useNavigate();
  const [events, setEvents] = useState<StaffStreamEvent[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!token) {
      nav("/staff/login");
      return;
    }
    const ac = new AbortController();
    setEvents([]);
    setErr("");
    (async () => {
      try {
        for await (const ev of streamSpectateEvents(token, convId, ac.signal)) {
          setEvents((prev) => [...prev, ev]);
        }
      } catch {
        if (!ac.signal.aborted) setErr("无法旁观（需 senior/engineer 权限）");
      }
    })();
    return () => {
      ac.abort();
    };
  }, [token, convId, nav]);

  return (
    <PageContainer fullHeight>
      <div className="mb-1 flex items-center gap-2">
        <h2 className="flex-1 text-sh2 text-ink-primary">旁观会话 #{convId}</h2>
        <Link to="/staff/conversations" className="text-body3 text-brand hover:underline">
          返回工作台
        </Link>
      </div>
      <div className="mb-3 text-footnote text-ink-secondary">
        只读模式{role ? `（${role}）` : ""} · 不接管、不发消息
      </div>
      {err && (
        <Alert variant="error" className="mb-2">
          {err}
        </Alert>
      )}
      <ul className="flex flex-1 flex-col gap-1 overflow-y-auto">
        {events.map((ev, i) => {
          const alert = ev.type === "tool_result" && (ev.empty || ev.ok === false);
          return (
            <li
              key={i}
              className={`text-body2 ${alert ? "text-status-error" : "text-ink-primary"}`}
            >
              {label(ev)}
              {ev.attachments?.length ? (
                <div className="mt-1 flex flex-wrap gap-2">
                  {ev.attachments.map((a) => (
                    <ImageThumb key={a.id} src={staffAttachmentUrl(convId, a.id)} />
                  ))}
                </div>
              ) : null}
            </li>
          );
        })}
        {events.length === 0 && !err && <EmptyState>等待会话活动…</EmptyState>}
      </ul>
    </PageContainer>
  );
}
