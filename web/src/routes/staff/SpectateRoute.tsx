import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { streamSpectateEvents, type StaffStreamEvent } from "../../api/staff";
import { useStaffSession } from "../../hooks/useStaffSession";

function label(ev: StaffStreamEvent): string {
  if (ev.type === "assistant_text") return `AI：${ev.content ?? ""}`;
  if (ev.type === "user_message") return `用户：${ev.content ?? ""}`;
  if (ev.type === "tool_call") return `调用工具：${ev.content ?? ""}`;
  if (ev.type === "mode_change") return `模式切换 → ${ev.to ?? ""}`;
  return `[${ev.type}] ${ev.content ?? ""}`;
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
    let stopped = false;
    (async () => {
      try {
        for await (const ev of streamSpectateEvents(token, convId)) {
          if (stopped) break;
          setEvents((prev) => [...prev, ev]);
        }
      } catch {
        setErr("无法旁观（需 senior/engineer 权限）");
      }
    })();
    return () => {
      stopped = true;
    };
  }, [token, convId, nav]);

  return (
    <div className="mx-auto flex h-full max-w-[720px] flex-col px-page py-block-lg">
      <h2 className="text-sh2 text-ink-primary mb-1">旁观会话 #{convId}</h2>
      <div className="text-footnote text-ink-secondary mb-3">
        只读模式{role ? `（${role}）` : ""} · 不接管、不发消息
      </div>
      {err && <div className="text-body3 text-status-error mb-2">{err}</div>}
      <ul className="flex-1 overflow-y-auto flex flex-col gap-1">
        {events.map((ev, i) => (
          <li key={i} className="text-body2 text-ink-primary">
            {label(ev)}
          </li>
        ))}
        {events.length === 0 && !err && (
          <li className="text-body3 text-ink-secondary">等待会话活动…</li>
        )}
      </ul>
    </div>
  );
}
