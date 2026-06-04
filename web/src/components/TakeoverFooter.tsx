import { Button, Divider, Drawer, Flex, Input, Select, Typography } from "antd";
import { MoreHorizontal, Send as SendIcon } from "lucide-react";
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

/**
 * 接管后底部操作区：移动优先 stacked 布局。
 *
 * 旧版三件套（📎 + Input + 发送）+ 另一行三件套（Select + 转派 + 标记已解决）在 H5 窄屏下被横向挤到不可用。
 * 现在：TextArea 独占一行（可多行），📎 / ⋯ / ▶ 排在下方行动栏；
 *       转派 + 标记已解决属低频二级操作，收进底部 Drawer，点 ⋯ 打开。
 */
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
  const [moreOpen, setMoreOpen] = useState(false);

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

  const canSend = !!draft.trim() || ids.length > 0;

  async function send() {
    if (!canSend) return;
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
    if (ok) {
      setMoreOpen(false);
      onReleased?.();
    }
  }

  async function resolve() {
    try {
      await resolveConversation(token, convId);
      onNotice("已标记解决并释放回 AI");
      setMoreOpen(false);
      onReleased?.();
    } catch {
      onNotice("标记失败，请重试");
    }
  }

  return (
    <>
      <Flex vertical gap="small">
        {/* TextArea 独占一行：autoSize 1～4 行自适应。
            Enter=发送 / Shift+Enter=换行，遵循聊天界面通用约定。 */}
        <Input.TextArea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="回复用户…"
          autoSize={{ minRows: 1, maxRows: 4 }}
          onPressEnter={(e) => {
            if (!e.shiftKey) {
              e.preventDefault();
              void send();
            }
          }}
        />

        {/* 行动栏：📎 左 / ⋯ + ▶ 右。窄屏下三件套不再争 Input 横向空间。 */}
        <Flex align="center" gap="small">
          <AttachButton
            upload={(f) => uploadStaffAttachment(convId, f, token)}
            ids={ids}
            onChange={setIds}
            max={MAX_IMAGES}
          />
          <div style={{ flex: 1 }} />
          <Button
            icon={<MoreHorizontal className="h-4 w-4" />}
            onClick={() => setMoreOpen(true)}
            aria-label="更多操作"
          />
          <Button
            type="primary"
            icon={<SendIcon className="h-4 w-4" />}
            onClick={() => void send()}
            disabled={!canSend}
          >
            发送
          </Button>
        </Flex>
      </Flex>

      {/* 转派 / 标记已解决 = 二级低频操作，收进底部抽屉。
          placement=bottom 在 H5 是大拇指自然触达区，桌面端也不突兀。 */}
      <Drawer
        title="更多操作"
        placement="bottom"
        open={moreOpen}
        onClose={() => setMoreOpen(false)}
        styles={{
          // antd v6 已废 `height` prop；这里用 wrapper 样式让抽屉随内容高度（≤60vh），
          // 避免默认 378px 在窄屏出现大片空白。
          wrapper: { height: "auto", maxHeight: "60vh" },
          body: { paddingBottom: 16 },
        }}
      >
        <Flex vertical gap="middle">
          <div>
            <Typography.Text
              type="secondary"
              style={{ fontSize: 12, display: "block", marginBottom: 6 }}
            >
              转派给客服
            </Typography.Text>
            <Flex gap="small">
              <Select
                value={target || undefined}
                onChange={(v) => setTarget(v ?? "")}
                placeholder={
                  candidates.length === 0
                    ? "暂无可转派目标"
                    : "选择转派目标客服…"
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
              <Button
                type="primary"
                onClick={transfer}
                disabled={!target.trim()}
              >
                转派
              </Button>
            </Flex>
          </div>

          <Divider style={{ margin: "4px 0" }} />

          <Button danger block onClick={resolve}>
            标记已解决
          </Button>
        </Flex>
      </Drawer>
    </>
  );
}
