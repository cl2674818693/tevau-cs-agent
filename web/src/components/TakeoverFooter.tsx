import { Button, Flex, Input } from "antd";
import { useState } from "react";

import { uploadStaffAttachment } from "../api/attachments";
import {
  resolveConversation,
  sendStaffMessage,
  transferConversation,
} from "../api/staff";

import { AttachButton } from "./AttachButton";

const MAX_IMAGES = 4;

type Props = {
  token: string;
  convId: number;
  onNotice: (msg: string) => void;
  /** 转派 / 标记已解决后，本客服不再持有会话，通知父组件复位接管态。 */
  onReleased?: () => void;
};

/** 接管后底部操作区：回复 / 转派 / 标记已解决。 */
export function TakeoverFooter({
  token,
  convId,
  onNotice,
  onReleased,
}: Props) {
  const [draft, setDraft] = useState("");
  const [target, setTarget] = useState("");
  const [ids, setIds] = useState<number[]>([]);

  async function send() {
    if (!draft.trim() && ids.length === 0) return;
    try {
      await sendStaffMessage(token, convId, draft.trim(), ids);
      // 不在本地乐观追加：消息由后端 human_message 事件经 SSE 回推统一显示，
      // 既避免与回推重复，也让旁观 / 其他客服端能看到这条回复。
      setDraft("");
      setIds([]);
    } catch {
      onNotice("发送失败，请重试");
    }
  }

  async function transfer() {
    if (!target.trim()) return;
    const ok = await transferConversation(token, convId, target.trim());
    onNotice(
      ok ? `已转派给 ${target.trim()}` : "转派失败（权限或目标不存在）",
    );
    setTarget("");
    if (ok) onReleased?.();
  }

  async function resolve() {
    try {
      await resolveConversation(token, convId);
      onNotice("已标记解决并释放回 AI");
      onReleased?.();
    } catch {
      onNotice("标记失败，请重试");
    }
  }

  return (
    <Flex vertical gap="small">
      <Flex align="center" gap="small">
        <AttachButton
          upload={(f) => uploadStaffAttachment(convId, f, token)}
          ids={ids}
          onChange={setIds}
          max={MAX_IMAGES}
        />
        <Input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="回复用户…"
          style={{ flex: 1 }}
          onPressEnter={send}
        />
        <Button
          type="primary"
          onClick={send}
          disabled={!draft.trim() && ids.length === 0}
        >
          发送
        </Button>
      </Flex>
      <Flex gap="small">
        <Input
          value={target}
          onChange={(e) => setTarget(e.target.value)}
          placeholder="转派给 staff_id…"
          style={{ flex: 1 }}
        />
        <Button type="text" onClick={transfer} disabled={!target.trim()}>
          转派
        </Button>
        <Button type="text" onClick={resolve}>
          标记已解决
        </Button>
      </Flex>
    </Flex>
  );
}
