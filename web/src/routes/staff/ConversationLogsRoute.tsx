import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  getConversationAudits,
  getConversationFeedback,
  getConversationMessages,
  type MessageFeedback,
  type StaffMessage,
  type ToolAudit,
} from "../../api/staff";
import { useStaffSession } from "../../hooks/useStaffSession";

/** 消息行的状态/判定徽章（失败、范围外判定等留痕信号）。 */
function MsgBadges({ m }: { m: StaffMessage }) {
  return (
    <>
      {m.status === "failed" && (
        <span className="ml-2 text-footnote text-status-error">failed:{m.error_code ?? "-"}</span>
      )}
      {m.status === "processing" && (
        <span className="ml-2 text-footnote text-status-warning">processing</span>
      )}
      {m.topic_verdict && m.topic_verdict !== "yes" && (
        <span className="ml-2 text-footnote text-ink-secondary">verdict:{m.topic_verdict}</span>
      )}
    </>
  );
}

// eslint-disable-next-line max-lines-per-function -- 留痕详情页：会话消息+工具审计+反馈三段视图
export function ConversationLogsRoute() {
  const { id } = useParams();
  const convId = Number(id);
  const { token } = useStaffSession();
  const nav = useNavigate();
  const [messages, setMessages] = useState<StaffMessage[]>([]);
  const [audits, setAudits] = useState<ToolAudit[]>([]);
  const [feedback, setFeedback] = useState<MessageFeedback[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!token) {
      nav("/staff/login");
      return;
    }
    Promise.all([
      getConversationMessages(token, convId),
      getConversationAudits(token, convId),
      getConversationFeedback(token, convId),
    ])
      .then(([m, a, f]) => {
        setMessages(m);
        setAudits(a);
        setFeedback(f);
      })
      .catch(() => setErr("加载失败"));
  }, [token, convId, nav]);

  return (
    <div className="mx-auto max-w-[860px] px-page py-block-lg">
      <div className="flex items-center mb-3">
        <h2 className="text-sh2 text-ink-primary flex-1">会话 #{convId} 留痕</h2>
        <Link to={`/staff/conversations/${convId}`} className="text-body3 text-ink-secondary">
          返回会话
        </Link>
      </div>
      {err && <div className="text-body3 text-status-error mb-2">{err}</div>}

      <h3 className="text-sh3 text-ink-primary mt-2 mb-1">消息历史</h3>
      <ul className="flex flex-col gap-1">
        {messages.map((m) => (
          <li key={m.id} className="rounded border border-line bg-surface-card px-3 py-2">
            <div className="text-footnote text-ink-secondary">
              {m.role} · {m.created_at}
              <MsgBadges m={m} />
            </div>
            <div className="text-body3 text-ink-primary whitespace-pre-wrap break-words">
              {m.content}
            </div>
          </li>
        ))}
        {messages.length === 0 && <li className="text-body3 text-ink-secondary">无消息</li>}
      </ul>

      <h3 className="text-sh3 text-ink-primary mt-4 mb-1">工具调用审计</h3>
      <ul className="flex flex-col gap-1">
        {audits.map((a) => (
          <li
            key={a.id}
            className="rounded border border-line bg-surface-card px-3 py-2 text-body3"
          >
            <span className="text-ink-primary">{a.tool_name}</span>
            <span className="ml-2 text-ink-secondary">{a.duration_ms}ms</span>
            <span
              className={
                a.is_empty === 1 || a.is_empty === true
                  ? "ml-2 text-status-error"
                  : "ml-2 text-ink-secondary"
              }
            >
              返回 {a.result_count ?? 0} 条
            </span>
            {a.subject_id ? (
              <span className="ml-2 text-ink-secondary">身份 {a.subject_id}</span>
            ) : null}
            {a.rejected ? (
              <span className="ml-2 text-status-error">被拒：{a.reject_reason ?? "-"}</span>
            ) : null}
            <div className="text-footnote text-ink-secondary break-words">{a.params_json}</div>
          </li>
        ))}
        {audits.length === 0 && <li className="text-body3 text-ink-secondary">无工具调用</li>}
      </ul>

      <h3 className="text-sh3 text-ink-primary mt-4 mb-1">反馈</h3>
      <ul className="flex flex-col gap-1">
        {feedback.map((f) => (
          <li
            key={f.id}
            className="rounded border border-line bg-surface-card px-3 py-2 text-body3"
          >
            <span className={f.rating === "down" ? "text-status-error" : "text-ink-primary"}>
              {f.rating === "down" ? "👎" : "👍"}
            </span>
            <span className="ml-2 text-ink-secondary">msg #{f.message_id}</span>
            {f.reason ? <span className="ml-2 text-ink-primary">{f.reason}</span> : null}
          </li>
        ))}
        {feedback.length === 0 && <li className="text-body3 text-ink-secondary">无反馈</li>}
      </ul>
    </div>
  );
}
