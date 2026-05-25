import { useEffect, useState } from "react";

import {
  approveAiDraft,
  disableAiDraft,
  enableAiDraft,
  rejectAiDraft,
  type StaffStreamEvent,
} from "../api/staff";

type UseAiDraft = {
  draftMode: boolean;
  aiDraft: string | null;
  toggleDraftMode: () => Promise<string>;
  approve: () => Promise<void>;
  reject: (rewrite: string) => Promise<void>;
};

/** 客服侧 AI 草稿模式状态机：开关 + 监听 ai_draft_ready + 审核动作。 */
export function useAiDraft(
  token: string | null,
  convId: number,
  events: StaffStreamEvent[],
  onNotice?: (msg: string) => void,
): UseAiDraft {
  const [draftMode, setDraftMode] = useState(false);
  const [aiDraft, setAiDraft] = useState<string | null>(null);

  useEffect(() => {
    const last = [...events].reverse().find((e) => e.type === "ai_draft_ready");
    if (last?.draft !== undefined) setAiDraft(last.draft);
  }, [events]);

  async function toggleDraftMode(): Promise<string> {
    if (!token) return "";
    try {
      if (draftMode) {
        await disableAiDraft(token, convId);
        setDraftMode(false);
        setAiDraft(null);
        return "已关闭 AI 草稿模式";
      }
      await enableAiDraft(token, convId);
      setDraftMode(true);
      return "已开启 AI 草稿模式：AI 出草稿，由你 review 后发送";
    } catch {
      return "操作失败，请重试";
    }
  }

  async function approve(): Promise<void> {
    if (!token) return;
    // 失败时不清空草稿，保留以便重试
    try {
      await approveAiDraft(token, convId);
      setAiDraft(null);
    } catch {
      onNotice?.("发送草稿失败，请重试");
    }
  }

  async function reject(rewrite: string): Promise<void> {
    if (!token) return;
    try {
      await rejectAiDraft(token, convId, rewrite);
      setAiDraft(null);
    } catch {
      onNotice?.("改写发送失败，请重试");
    }
  }

  return { draftMode, aiDraft, toggleDraftMode, approve, reject };
}
