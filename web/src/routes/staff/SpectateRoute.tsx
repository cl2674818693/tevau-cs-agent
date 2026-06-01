import { Alert, Button, Empty, Flex, Tag, Typography } from "antd";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { staffAttachmentUrl } from "../../api/attachments";
import { streamSpectateEvents, type StaffStreamEvent } from "../../api/staff";
import { ImageThumb } from "../../components/ImageThumb";
import { useStaffSession } from "../../hooks/useStaffSession";

const { Text } = Typography;

// 旁观流事件 → 可读文案。后端旁观流发的是 tool_use（带 name/input），不是 tool_call/content。
const LABELERS: Record<string, (ev: StaffStreamEvent) => string> = {
  assistant_text: (ev) => `AI：${ev.content ?? ""}`,
  user_message: (ev) => `用户：${ev.content ?? ""}`,
  human_message: (ev) => `客服：${ev.content ?? ""}`,
  tool_use: (ev) =>
    `调用工具：${ev.name ?? ""}${ev.input ? ` ${JSON.stringify(ev.input)}` : ""}`,
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
    <div className="flex h-screen flex-col" style={{ background: "#fff" }}>
      <Flex
        align="center"
        gap="middle"
        style={{
          height: 48,
          padding: "0 16px",
          borderBottom: "1px solid #f0f0f0",
        }}
      >
        <Link to="/staff/conversations">
          <Button type="text" size="small">
            返回工作台
          </Button>
        </Link>
        <Text strong style={{ flex: 1 }}>
          旁观 #{convId}
        </Text>
        <Tag>只读{role ? ` · ${role}` : ""}</Tag>
      </Flex>

      <div
        className="flex flex-1 flex-col overflow-hidden"
        style={{ padding: "12px 16px" }}
      >
        {err && (
          <Alert
            type="error"
            showIcon
            title={err}
            style={{ marginBottom: 8 }}
          />
        )}
        <ul
          className="flex flex-1 flex-col gap-1 overflow-y-auto"
          style={{ margin: 0, padding: 0, listStyle: "none" }}
        >
          {events.map((ev, i) => {
            const alert = ev.type === "tool_result" && (ev.empty || ev.ok === false);
            return (
              <li
                key={i}
                style={{
                  fontSize: 13,
                  color: alert ? "#dc2626" : "rgba(0,0,0,0.85)",
                }}
              >
                {label(ev)}
                {ev.attachments?.length ? (
                  <div className="mt-1 flex flex-wrap gap-2">
                    {ev.attachments.map((a) => (
                      <ImageThumb
                        key={a.id}
                        src={staffAttachmentUrl(convId, a.id)}
                      />
                    ))}
                  </div>
                ) : null}
              </li>
            );
          })}
          {events.length === 0 && !err && (
            <Empty description="等待会话活动…" />
          )}
        </ul>
      </div>
    </div>
  );
}
