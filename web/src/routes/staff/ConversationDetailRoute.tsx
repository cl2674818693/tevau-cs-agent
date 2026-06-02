import { Alert, Breadcrumb, Button, Card, Flex, Skeleton, Space, Typography } from "antd";
import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  getConversationMessages,
  getStaffConversation,
  releaseConversation,
  type StaffConversation,
  type StaffMessage,
  streamStaffEvents,
  takeConversation,
  type StaffStreamEvent,
} from "../../api/staff";
import { AiDraftPanel } from "../../components/AiDraftPanel";
import { AiToolsPanel } from "../../components/AiToolsPanel";
import { ConversationInfoCard } from "../../components/ConversationInfoCard";
import { EventBubble } from "../../components/EventBubble";
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

/** 拉单会话信息（含风险标记），同时给右侧 InfoCard 用 + 初始化接管态。
 *  SSE mode_change / transferred 事件来了乐观更新 conv，避免刷页面才看到接管/转派。 */
function useConvInfo(
  token: string | null,
  staffId: string | null,
  convId: number,
  events: StaffStreamEvent[],
  setTaken: (b: boolean) => void,
): { conv: StaffConversation | null; loading: boolean } {
  const [conv, setConv] = useState<StaffConversation | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    setLoading(true);
    getStaffConversation(token, convId)
      .then((c) => {
        if (cancelled) return;
        setConv(c);
        if (staffId)
          setTaken(c.mode === "human_takeover" && c.assigned_staff_id === staffId);
      })
      .catch(() => {
        /* 取不到状态时保持未接管 */
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token, staffId, convId, setTaken]);

  // 实时事件 → 局部更新 conv.mode/assigned_staff_id，让 InfoCard 不必刷页面。
  // 关键：mode_change 的 by_staff_id 是"触发操作的人"（接管者/释放者/解决者），
  // 不是负责人。只有 to=human_takeover 时它才 = 新负责人；to=ai/human_pending
  // 时（release/resolved）必须清空 assigned；ai_draft 切换不影响负责人。
  useEffect(() => {
    const last = events[events.length - 1];
    if (!last) return;
    if (last.type === "mode_change" && last.to) {
      const to = last.to;
      setConv((prev) => {
        if (!prev) return prev;
        const assigned =
          to === "human_takeover"
            ? (last.by_staff_id ?? prev.assigned_staff_id)
            : to === "ai" || to === "human_pending"
              ? null
              : prev.assigned_staff_id;
        return { ...prev, mode: to, assigned_staff_id: assigned };
      });
    }
    if (last.type === "transferred")
      setConv((prev) =>
        prev ? { ...prev, mode: "human_takeover", assigned_staff_id: last.to_staff_id ?? null } : prev,
      );
  }, [events]);

  return { conv, loading };
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
  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const didInitialScrollRef = useRef(false);

  // IM 标准滚动：用户在底部才自动滚（不打断翻阅）；首次历史回放完用瞬时滚，
  // 后续 SSE 增量用平滑。底部判定阈值 80px 容忍小幅滚动。
  useEffect(() => {
    if (events.length === 0) return;
    const el = scrollRef.current;
    if (!el) return;
    const nearBottom =
      el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    const first = !didInitialScrollRef.current;
    if (first || nearBottom) {
      bottomRef.current?.scrollIntoView({
        behavior: first ? "auto" : "smooth",
        block: "end",
      });
      didInitialScrollRef.current = true;
    }
  }, [events.length]);

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
    <div
      ref={scrollRef}
      className="flex flex-1 flex-col overflow-y-auto"
      style={{ padding: "8px 4px", gap: 10 }}
    >
      {events.map((ev, i) => (
        <EventBubble key={i} ev={ev} convId={convId} token={token} />
      ))}
      <div ref={bottomRef} />
    </div>
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

  const { conv, loading: convLoading } = useConvInfo(
    token,
    staffId,
    convId,
    events,
    setTaken,
  );

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
          title="对话"
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
            overflowY: "auto",
          }}
        >
          <ConversationInfoCard conv={conv} loading={convLoading} />
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
