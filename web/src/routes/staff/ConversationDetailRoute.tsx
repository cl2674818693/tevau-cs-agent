import { Alert, Breadcrumb, Button, Card, Flex, Skeleton, Space, Typography } from "antd";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { staffAttachmentUrl } from "../../api/attachments";
import {
  getConversationMessages,
  getStaffConversation,
  releaseConversation,
  type StaffMessage,
  streamStaffEvents,
  takeConversation,
  type StaffStreamEvent,
} from "../../api/staff";
import { AiDraftPanel } from "../../components/AiDraftPanel";
import { AiToolsPanel } from "../../components/AiToolsPanel";
import { StaffImageThumb } from "../../components/StaffImageThumb";
import { TakeoverFooter } from "../../components/TakeoverFooter";
import { useAiDraft } from "../../hooks/useAiDraft";
import { useStaffSession } from "../../hooks/useStaffSession";

/** 把 messages 表的历史消息映射成事件流条目；ai_draft / 未知 role 过滤掉。
 *  不填 draft 字段，避免 useAiDraft 把历史草稿误判成新草稿弹出。 */
function messageToStreamEvent(m: StaffMessage): StaffStreamEvent | null {
  const typeByRole: Record<string, string> = {
    user: "user_message",
    assistant: "assistant_message",
    human_agent: "human_message",
  };
  const type = typeByRole[m.role];
  if (!type) return null;
  return { type, content: m.content, attachments: m.attachments };
}

/**
 * 订阅会话事件总线，返回累积的事件列表（含 mount 前的历史 + SSE 增量）。
 * stopped 必须是 effect 闭包内的局部变量，不能用 useRef：StrictMode 下 effect 会
 * mount→unmount→mount，两次 mount 共享同一个 ref，第二次 mount 会把 stopped 重置成
 * false，导致第一个订阅的 for-await 永不 break → 双订阅 → 每个事件被 push 两次。
 *
 * 历史 prepend 而非覆盖：SSE 可能先返回事件，历史晚到，prepend 保证时序正确不丢新事件。
 * 历史 / SSE 接缝处可能有短暂重叠（同一条消息被回放又被推送），暂不去重——
 * 极端情况下用户看到重复气泡，刷新即可消除，避免引入 message_id 同步开销。
 */
function useStaffStream(
  token: string | null,
  convId: number,
): { events: StaffStreamEvent[]; historyLoading: boolean } {
  const [events, setEvents] = useState<StaffStreamEvent[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  useEffect(() => {
    if (!token) return;
    let stopped = false;
    setHistoryLoading(true);
    setEvents([]);

    getConversationMessages(token, convId, { limit: 100 })
      .then((page) => {
        if (stopped) return;
        const history = page.messages
          .map(messageToStreamEvent)
          .filter((e): e is StaffStreamEvent => e !== null);
        setEvents((prev) => [...history, ...prev]);
      })
      .catch(() => {
        /* 历史拉失败不影响 SSE 增量展示 */
      })
      .finally(() => {
        if (!stopped) setHistoryLoading(false);
      });

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
  return { events, historyLoading };
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
        if (!cancelled)
          setTaken(
            c.mode === "human_takeover" && c.assigned_staff_id === staffId,
          );
      })
      .catch(() => {
        /* 取不到状态时保持未接管 */
      });
    return () => {
      cancelled = true;
    };
  }, [token, staffId, convId, setTaken]);
}

function EventLog({
  events,
  historyLoading,
  convId,
  token,
}: {
  events: StaffStreamEvent[];
  historyLoading: boolean;
  convId: number;
  token: string | null;
}) {
  // mount 时先回放历史消息（user/assistant/human_agent），之后续 SSE 增量。
  if (historyLoading && events.length === 0) {
    return (
      <div style={{ padding: 16 }}>
        <Skeleton active paragraph={{ rows: 4 }} />
      </div>
    );
  }
  if (events.length === 0) {
    return (
      <div
        className="flex flex-1 items-center justify-center"
        style={{ padding: 16 }}
      >
        <Typography.Text type="secondary" style={{ fontSize: 12, textAlign: "center" }}>
          该会话暂无消息。
          <br />
          完整留痕（工具调用 / 反馈）请查看{" "}
          <Link to={`/staff/conversations/${convId}/logs`}>会话日志</Link>
        </Typography.Text>
      </div>
    );
  }
  return (
    <ul
      className="flex flex-1 flex-col overflow-y-auto"
      style={{ margin: 0, padding: 0, listStyle: "none", gap: 6 }}
    >
      {events.map((ev, i) => (
        <li
          key={i}
          style={{ fontSize: 13, lineHeight: 1.6 }}
        >
          <span
            style={{
              marginRight: 6,
              fontSize: 12,
              fontFamily: "ui-monospace, monospace",
              color: "rgba(0,0,0,0.45)",
            }}
          >
            [{ev.type}]
          </span>
          {ev.content ?? ev.to ?? ""}
          {ev.attachments?.length && token ? (
            <Flex wrap="wrap" gap="small" style={{ marginTop: 4 }}>
              {ev.attachments.map((a) => (
                <StaffImageThumb
                  key={a.id}
                  src={staffAttachmentUrl(convId, a.id)}
                  token={token}
                />
              ))}
            </Flex>
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
  const { events, historyLoading } = useStaffStream(token, convId);
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
    <div
      className="flex h-full flex-col"
      style={{ gap: 16, padding: "20px 24px" }}
    >
      <Flex justify="space-between" align="center" gap="middle">
        <Breadcrumb
          items={[
            { title: <Link to="/staff/conversations">会话列表</Link> },
            { title: <span style={{ fontWeight: 500 }}>会话 #{convId}</span> },
          ]}
        />
        <Space>
          <Button onClick={onToggleDraftMode}>
            {draftMode ? "关闭草稿模式" : "AI 草稿模式"}
          </Button>
          {taken ? (
            <Button onClick={onRelease}>释放回 AI</Button>
          ) : (
            <Button type="primary" onClick={onTake}>
              接管
            </Button>
          )}
        </Space>
      </Flex>

      {notice && <Alert type="info" showIcon title={notice} />}

      <Flex gap="middle" style={{ flex: 1, minHeight: 0 }}>
        <Card
          title="事件流"
          size="small"
          style={{ flex: 1, display: "flex", flexDirection: "column" }}
          styles={{
            body: {
              display: "flex",
              flexDirection: "column",
              gap: 12,
              flex: 1,
              minHeight: 0,
              overflow: "hidden",
            },
          }}
        >
          <EventLog
            events={events}
            historyLoading={historyLoading}
            convId={convId}
            token={token}
          />
          {taken && token && (
            <div
              style={{
                flexShrink: 0,
                borderTop: "1px solid #f0f0f0",
                paddingTop: 12,
              }}
            >
              <TakeoverFooter
                token={token}
                convId={convId}
                onNotice={setNotice}
                onReleased={() => setTaken(false)}
              />
            </div>
          )}
        </Card>

        <div
          style={{
            width: 320,
            flexShrink: 0,
            display: "flex",
            flexDirection: "column",
            gap: 16,
          }}
        >
          <AiDraftPanel
            draft={aiDraft}
            onApprove={approve}
            onReject={reject}
          />
          {canUseTools && token && (
            <AiToolsPanel token={token} convId={convId} />
          )}
        </div>
      </Flex>
    </div>
  );
}
