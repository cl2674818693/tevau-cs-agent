import { Button, Flex, Input, Select } from "antd";
import { useEffect, useState } from "react";

import { uploadStaffAttachment } from "../api/attachments";
import {
  listTransferCandidates,
  resolveConversation,
  sendStaffMessage,
  type TransferCandidate,
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
  const [candidates, setCandidates] = useState<TransferCandidate[]>([]);

  // 拉转派目标候选（active 客服，已过滤当前用户 + agent 限 engineer）。
  // 转派窗口默认关闭，仅 mount 时拉一次足够；目标新增/下线属罕见事件，不做轮询。
  useEffect(() => {
    let cancelled = false;
    listTransferCandidates(token)
      .then((cs) => {
        if (!cancelled) setCandidates(cs);
      })
      .catch(() => {
        /* 拉失败时下拉空，不阻塞回复 */
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

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
      {/* wrap="wrap" 让 AttachButton 的缩略图行（w-full）自然换到上方一行，
          否则会和 Input 横向争空间把输入框压到几乎不可用。 */}
      <Flex align="center" gap="small" wrap="wrap">
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
          style={{ flex: 1, minWidth: 200 }}
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
        <Select
          value={target || undefined}
          onChange={(v) => setTarget(v ?? "")}
          placeholder={
            candidates.length === 0 ? "暂无可转派目标" : "选择转派目标客服…"
          }
          showSearch
          allowClear
          optionFilterProp="label"
          style={{ flex: 1 }}
          disabled={candidates.length === 0}
          options={candidates.map((c) => ({
            value: c.staff_id,
            label: `${c.display_name}（${c.staff_id}） · ${c.role}`,
          }))}
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
