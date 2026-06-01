import { Button, Card, Flex, Input, Typography } from "antd";
import { useEffect, useState } from "react";

const { TextArea } = Input;
const { Text } = Typography;

type Props = {
  draft: string | null;
  onApprove: () => void | Promise<void>;
  onReject: (rewrite: string) => void | Promise<void>;
};

/** 客服 review AI 草稿：直接发出，或改写后发。 */
export function AiDraftPanel({ draft, onApprove, onReject }: Props) {
  const [rewrite, setRewrite] = useState("");
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    setRewrite(draft ?? "");
    setEditing(false);
  }, [draft]);

  if (draft === null) return null;

  return (
    <Card
      size="small"
      style={{ background: "rgba(0, 0, 0, 0.02)" }}
      title={
        <Text type="secondary" style={{ fontSize: 12 }}>
          AI 草稿（未发送）
        </Text>
      }
    >
      {editing ? (
        <TextArea
          value={rewrite}
          onChange={(e) => setRewrite(e.target.value)}
          rows={4}
          style={{ fontSize: 13 }}
        />
      ) : (
        <div style={{ whiteSpace: "pre-wrap", fontSize: 13 }}>{draft}</div>
      )}
      <Flex gap="small" style={{ marginTop: 8 }}>
        {editing ? (
          <Button
            type="primary"
            size="small"
            onClick={() => onReject(rewrite.trim())}
            disabled={!rewrite.trim()}
          >
            改写后发送
          </Button>
        ) : (
          <>
            <Button type="primary" size="small" onClick={() => onApprove()}>
              直接发出
            </Button>
            <Button type="text" size="small" onClick={() => setEditing(true)}>
              改写
            </Button>
          </>
        )}
      </Flex>
    </Card>
  );
}
