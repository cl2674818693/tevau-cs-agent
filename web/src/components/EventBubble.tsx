import { Avatar, Flex, Typography } from "antd";
import ReactMarkdown from "react-markdown";

import { safeMarkdownProps } from "@/lib/markdown-safe";

import { staffAttachmentUrl } from "../api/attachments";
import type { StaffMessage, StaffStreamEvent } from "../api/staff";

import { StaffImageThumb } from "./StaffImageThumb";

/** 把 messages 表里的历史消息映射成事件流条目；ai_draft / 未知 role 过滤掉。
 *  不填 draft 字段，避免 useAiDraft 把历史草稿误判成新草稿弹出。
 *  详情页和日志页共用。
 *
 *  纯空 assistant 行同时过滤：AI 做纯工具调用回合（无伴随文字）时，runtime 把 content
 *  落库为 json.dumps([])，留痕接口还原后是 ""，渲染出来是只有头像+时间戳的空气泡。
 *  与 C 端 conversations.py:119 的口径对齐（`if not content and not atts: continue`）。*/
export function messageToStreamEvent(m: StaffMessage): StaffStreamEvent | null {
  const typeByRole: Record<string, string> = {
    user: "user_message",
    assistant: "assistant_message",
    human_agent: "human_message",
  };
  const type = typeByRole[m.role];
  if (!type) return null;
  const hasAttachments = !!m.attachments && m.attachments.length > 0;
  if (!m.content && !hasAttachments) return null;
  return { type, content: m.content, attachments: m.attachments };
}

const { Text } = Typography;

/**
 * Admin 端事件流气泡：用户在左、AI/客服在右；系统事件 / 工具调用居中胶囊。
 *
 * 设计取舍（与 H5 MessageBubble 不同）：
 * - 客服视角：user_message 在左（对方），assistant_message + human_message 在右（己方）
 * - tool_use / tool_result 用居中灰胶囊：让客服知道 AI 调了什么，不抢主对话视线
 * - 不复用 H5 MessageBubble：那是 Message 类型 + 用户鉴权解析器，强行接入污染严重
 * - 图片走 StaffImageThumb（带 staff Bearer 鉴权 + antd Image 预览工具栏）
 */
export function EventBubble({
  ev,
  convId,
  token,
}: {
  ev: StaffStreamEvent;
  convId: number;
  token: string | null;
}) {
  switch (ev.type) {
    case "user_message":
      return (
        <UserBubble
          content={ev.content ?? ""}
          attachments={ev.attachments}
          convId={convId}
          token={token}
        />
      );
    case "assistant_message":
    case "assistant_text":
      return <AssistantBubble content={ev.content ?? ""} />;
    case "human_message":
      return (
        <HumanBubble
          content={ev.content ?? ""}
          attachments={ev.attachments}
          convId={convId}
          token={token}
        />
      );
    case "tool_use":
      return (
        <CenterChip
          tone="muted"
          text={`调用 ${ev.name ?? "tool"}${
            ev.input ? ` · ${truncate(JSON.stringify(ev.input), 60)}` : ""
          }`}
        />
      );
    case "tool_result": {
      const fail = ev.ok === false || ev.empty;
      const cnt = ev.result_count ?? 0;
      return (
        <CenterChip
          tone={fail ? "warning" : "muted"}
          text={`${ev.name ?? "tool"} 返回 ${cnt} 条${ev.empty ? "（空）" : ""}${
            ev.ok === false ? "（失败）" : ""
          }`}
        />
      );
    }
    case "mode_change":
      return <CenterChip tone="info" text={`切换到 ${labelMode(ev.to)}`} />;
    case "transferred":
      return (
        <CenterChip tone="info" text={`转派给 ${ev.to_staff_id ?? "—"}`} />
      );
    case "request_human":
      return <CenterChip tone="warning" text="用户已请求人工" />;
    case "ai_draft_ready":
      return <CenterChip tone="muted" text="AI 草稿已就绪（待你 review）" />;
    case "error":
      return (
        <CenterChip tone="error" text={`错误：${ev.content ?? "未知"}`} />
      );
    default:
      // 兜底：未知事件类型仍可见（含本次新加的 pending_takeover_timeout 等）
      return (
        <CenterChip tone="muted" text={`[${ev.type}] ${ev.content ?? ""}`} />
      );
  }
}

function labelMode(to: string | undefined): string {
  switch (to) {
    case "human_takeover":
      return "人工接管";
    case "human_pending":
      return "等待人工";
    case "ai":
      return "AI";
    case "ai_draft":
      return "AI 草稿模式";
    default:
      return to ?? "—";
  }
}

function truncate(s: string, max: number): string {
  return s.length <= max ? s : s.slice(0, max) + "…";
}

function UserBubble({
  content,
  attachments,
  convId,
  token,
}: {
  content: string;
  attachments?: { id: number; mime: string }[];
  convId: number;
  token: string | null;
}) {
  return (
    <Flex gap="small" align="flex-start" style={{ maxWidth: "100%" }}>
      <Avatar
        size={32}
        style={{ background: "#e5e7eb", color: "#4b5563", flexShrink: 0 }}
      >
        U
      </Avatar>
      <Flex
        vertical
        gap={4}
        style={{ maxWidth: "75%", minWidth: 0, alignItems: "flex-start" }}
      >
        <Text type="secondary" style={{ fontSize: 11 }}>
          用户
        </Text>
        {content && (
          <div
            style={{
              background: "#f3f4f6",
              borderRadius: "8px 8px 8px 2px",
              padding: "8px 12px",
              fontSize: 13,
              lineHeight: 1.6,
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
            }}
          >
            {content}
          </div>
        )}
        <Attachments
          atts={attachments}
          convId={convId}
          token={token}
          align="left"
        />
      </Flex>
    </Flex>
  );
}

function AssistantBubble({ content }: { content: string }) {
  return (
    <Flex
      gap="small"
      align="flex-start"
      style={{ maxWidth: "100%", justifyContent: "flex-end" }}
    >
      <Flex
        vertical
        gap={4}
        style={{ maxWidth: "75%", minWidth: 0, alignItems: "flex-end" }}
      >
        <Text type="secondary" style={{ fontSize: 11 }}>
          AI
        </Text>
        <div
          className="markdown-body-dark"
          style={{
            background: "#eef2ff",
            color: "#1e1b4b",
            borderRadius: "8px 8px 2px 8px",
            padding: "8px 12px",
            fontSize: 13,
            lineHeight: 1.6,
            wordBreak: "break-word",
          }}
        >
          {/* 与 H5 MessageBubble 对齐：AI 回复走 markdown 渲染（粗体 / 代码 / 表格 / 列表）。
              admin 端之前用纯 pre-wrap 显示 ** 和 ` 原文，与用户端不一致。 */}
          <ReactMarkdown
            {...safeMarkdownProps}
            components={{
              table: ({ node: _node, ...props }) => (
                <div style={{ overflowX: "auto" }}>
                  <table {...props} />
                </div>
              ),
            }}
          >
            {content}
          </ReactMarkdown>
        </div>
      </Flex>
      <Avatar
        shape="square"
        size={32}
        style={{ background: "#4f46e5", color: "#fff", fontWeight: 700, flexShrink: 0 }}
      >
        T
      </Avatar>
    </Flex>
  );
}

function HumanBubble({
  content,
  attachments,
  convId,
  token,
}: {
  content: string;
  attachments?: { id: number; mime: string }[];
  convId: number;
  token: string | null;
}) {
  return (
    <Flex
      gap="small"
      align="flex-start"
      style={{ maxWidth: "100%", justifyContent: "flex-end" }}
    >
      <Flex
        vertical
        gap={4}
        style={{ maxWidth: "75%", minWidth: 0, alignItems: "flex-end" }}
      >
        <Text type="secondary" style={{ fontSize: 11 }}>
          客服
        </Text>
        {content && (
          <div
            style={{
              background: "#fff7ed",
              color: "#7c2d12",
              border: "1px solid rgba(217,119,6,0.3)",
              borderRadius: "8px 8px 2px 8px",
              padding: "8px 12px",
              fontSize: 13,
              lineHeight: 1.6,
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
            }}
          >
            {content}
          </div>
        )}
        <Attachments
          atts={attachments}
          convId={convId}
          token={token}
          align="right"
        />
      </Flex>
      <Avatar
        shape="square"
        size={32}
        style={{ background: "#fff7ed", color: "#d97706", fontWeight: 700, flexShrink: 0 }}
      >
        客
      </Avatar>
    </Flex>
  );
}

function Attachments({
  atts,
  convId,
  token,
  align,
}: {
  atts?: { id: number; mime: string }[];
  convId: number;
  token: string | null;
  align: "left" | "right";
}) {
  if (!atts?.length || !token) return null;
  return (
    <Flex
      wrap="wrap"
      gap="small"
      style={{ justifyContent: align === "right" ? "flex-end" : "flex-start" }}
    >
      {atts.map((a) => (
        <StaffImageThumb
          key={a.id}
          src={staffAttachmentUrl(convId, a.id)}
          token={token}
          size={80}
        />
      ))}
    </Flex>
  );
}

const CHIP_TONE = {
  muted: { bg: "#f3f4f6", color: "#6b7280" },
  info: { bg: "#e0f2fe", color: "#075985" },
  warning: { bg: "#fff7ed", color: "#9a3412" },
  error: { bg: "#fee2e2", color: "#991b1b" },
} as const;

function CenterChip({
  text,
  tone,
}: {
  text: string;
  tone: keyof typeof CHIP_TONE;
}) {
  const { bg, color } = CHIP_TONE[tone];
  return (
    <Flex justify="center">
      <span
        style={{
          background: bg,
          color,
          borderRadius: 999,
          padding: "3px 12px",
          fontSize: 11,
          fontFamily: "ui-monospace, monospace",
        }}
      >
        {text}
      </span>
    </Flex>
  );
}
