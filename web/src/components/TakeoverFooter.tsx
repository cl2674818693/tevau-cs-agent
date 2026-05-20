import { useState } from "react";

import {
  resolveConversation,
  sendStaffMessage,
  transferConversation,
  type StaffStreamEvent,
} from "../api/staff";
import { Button } from "./ui/button";

type Props = {
  token: string;
  convId: number;
  onLocalEvent: (e: StaffStreamEvent) => void;
  onNotice: (msg: string) => void;
};

/** 接管后底部操作区：回复 / 转派 / 标记已解决。 */
export function TakeoverFooter({ token, convId, onLocalEvent, onNotice }: Props) {
  const [draft, setDraft] = useState("");
  const [target, setTarget] = useState("");

  async function send() {
    if (!draft.trim()) return;
    await sendStaffMessage(token, convId, draft.trim());
    onLocalEvent({ type: "human_message", content: draft.trim() });
    setDraft("");
  }

  async function transfer() {
    if (!target.trim()) return;
    const ok = await transferConversation(token, convId, target.trim());
    onNotice(ok ? `已转派给 ${target.trim()}` : "转派失败（权限或目标不存在）");
    setTarget("");
  }

  async function resolve() {
    await resolveConversation(token, convId);
    onNotice("已标记解决并释放回 AI");
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex gap-2">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="回复用户…"
          className="flex-1 rounded border border-line px-3 py-2 text-body1 outline-none"
        />
        <Button size="md" onClick={send} disabled={!draft.trim()}>
          发送
        </Button>
      </div>
      <div className="flex gap-2">
        <input
          value={target}
          onChange={(e) => setTarget(e.target.value)}
          placeholder="转派给 staff_id…"
          className="flex-1 rounded border border-line px-3 py-2 text-body3 outline-none"
        />
        <Button size="sm" variant="ghost" onClick={transfer} disabled={!target.trim()}>
          转派
        </Button>
        <Button size="sm" variant="ghost" onClick={resolve}>
          标记已解决
        </Button>
      </div>
    </div>
  );
}
