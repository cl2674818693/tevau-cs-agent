import { Alert, Breadcrumb, Button, Card, Skeleton, Space, Typography } from "antd";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  getConversationMessages,
  getStaffConversation,
  releaseConversation,
  type StaffConversation,
  streamStaffEvents,
  takeConversation,
  type StaffStreamEvent,
} from "../../api/staff";
import { AiDraftPanel } from "../../components/AiDraftPanel";
import { AiToolsPanel } from "../../components/AiToolsPanel";
import { EventBubble, messageToStreamEvent } from "../../components/EventBubble";
import { SubjectInfoCard } from "../../components/SubjectInfoCard";
import { TakeoverFooter } from "../../components/TakeoverFooter";
import { useAiDraft } from "../../hooks/useAiDraft";
import { useStaffSession } from "../../hooks/useStaffSession";

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
): {
  conv: StaffConversation | null;
  loading: boolean;
  refetch: () => Promise<void>;
} {
  const [conv, setConv] = useState<StaffConversation | null>(null);
  const [loading, setLoading] = useState(true);

  // "我是否接管"只看 assigned_staff_id===staffId，不挂 mode：human_takeover →
  // ai_draft（客服自己开启草稿模式）后 mode 变了，但 assigned 还是自己，按钮应继续
  // 显示"释放回 AI"，而不是错误地回到"接管"。
  const isMine = (c: StaffConversation): boolean =>
    !!staffId && c.assigned_staff_id === staffId;

  const refetch = useCallback(async () => {
    if (!token) return;
    try {
      const c = await getStaffConversation(token, convId);
      setConv(c);
      setTaken(isMine(c));
    } catch {
      /* 取不到时保持当前态 */
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, convId, staffId, setTaken]);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    setLoading(true);
    getStaffConversation(token, convId)
      .then((c) => {
        if (cancelled) return;
        setConv(c);
        setTaken(isMine(c));
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, staffId, convId, setTaken]);

  // conv 任何来源的变化（SSE mode_change / transferred / refetch）都立刻同步 taken。
  // 否则别人 release 后 conv.assigned_staff_id 变 null、taken 仍 true，TakeoverFooter
  // 继续显示、客服点发送 → 后端 mode!=human_takeover 直接 403。
  useEffect(() => {
    if (conv) setTaken(isMine(conv));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conv?.assigned_staff_id, conv?.mode, staffId]);

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

  return { conv, loading, refetch };
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
          完整日志（工具调用 / 反馈）请查看{" "}
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

  const { conv, refetch: refetchConv } = useConvInfo(
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
    // 失败 = 后端已 human_takeover，但本地 conv 可能还是 ai/human_pending 没及时同步。
    // 强制 refetch，让按钮立刻进入"已被 X 接管"禁用态，避免用户反复点同一个按钮。
    if (!ok) await refetchConv();
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

  // 接管按钮三态：未接管(可点) / 我接管(显示释放) / 他人接管(禁用)。
  // 判定基于 assigned_staff_id 而不是 mode：ai_draft 也是"已接管"的子状态
  // （客服接管后开草稿模式），assigned 仍指向接管者。挂 mode 会让 ai_draft
  // 状态下负责人按钮错回"接管"，点了 409。
  // staffId 拿不到时(JWT 解析失败)不进入"他人接管"分支，回退到可点的"接管"，
  // 让后端 409 兜底拒绝——比 UI 永远禁用更安全。
  const otherStaffTook =
    !!staffId &&
    !!conv &&
    !!conv.assigned_staff_id &&
    conv.assigned_staff_id !== staffId;

  return (
    // AppShell 用 minHeight:100vh（可超出），h-full 子页面没有具体高度边界，
    // EventLog 的 overflow-y-auto 失效会让对话区无限撑高。固定 = 100vh -
    // AppShell.Header(56px) 让 flex 链路 minHeight:0 真正约束 EventLog 滚动。
    //
    // 移动端（< md）：Sider 自动折叠成 0，整屏给 Content。布局切纵向，对话卡占
    // 主体（flex:1），InfoCard/Draft/Tools 折到下方并限高自滚，避免 320 右栏在
    // 窄屏被并排压扁。
    <div
      className="flex flex-col gap-3 p-3 md:gap-4 md:p-5"
      style={{ height: "calc(100vh - 56px)" }}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Breadcrumb
          items={[
            { title: <Link to="/staff/conversations">会话列表</Link> },
            { title: <span style={{ fontWeight: 500 }}>会话 #{convId}</span> },
          ]}
        />
        {/* H5 窄屏下两个状态按钮 size=small，避免吃掉两行垂直空间 */}
        <Space wrap size={[8, 8]}>
          <Button size="small" onClick={onToggleDraftMode} disabled={otherStaffTook}>
            {draftMode ? "关闭草稿模式" : "AI 草稿模式"}
          </Button>
          {taken ? (
            <Button size="small" onClick={onRelease}>
              释放回 AI
            </Button>
          ) : otherStaffTook ? (
            <Button size="small" disabled>
              已被 {conv?.assigned_staff_id} 接管
            </Button>
          ) : (
            <Button size="small" type="primary" onClick={onTake}>
              接管
            </Button>
          )}
        </Space>
      </div>

      {notice && <Alert type="info" showIcon title={notice} />}
      {otherStaffTook && !notice && (
        <Alert
          type="info"
          showIcon
          title={`该会话已被 ${conv?.assigned_staff_id} 接管，你处于只读状态`}
        />
      )}

      <div className="flex flex-1 min-h-0 flex-col gap-3 md:flex-row md:gap-4">
        <Card
          title="对话"
          size="small"
          style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column" }}
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

        {/* 桌面 320px 固定右栏；移动端整宽，限高 40vh 自滚，避免吃掉对话区 */}
        <div className="flex flex-col gap-3 overflow-y-auto md:w-[320px] md:flex-shrink-0 md:max-h-none max-h-[40vh]">
          <SubjectInfoCard token={token} convId={convId} />
          <AiDraftPanel
            draft={aiDraft}
            onApprove={approve}
            onReject={reject}
          />
          {canUseTools && token && (
            <AiToolsPanel token={token} convId={convId} />
          )}
        </div>
      </div>
    </div>
  );
}
