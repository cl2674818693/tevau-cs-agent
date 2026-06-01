import { useEffect, useState } from "react";

import { Button } from "./ui/button";
import { Textarea } from "./ui/input";

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
    <div className="rounded-lg border border-border bg-muted/40 p-3">
      <div className="mb-1.5 text-xs font-medium text-muted-foreground">AI 草稿（未发送）</div>
      {editing ? (
        <Textarea
          value={rewrite}
          onChange={(e) => setRewrite(e.target.value)}
          rows={4}
          className="text-sm"
        />
      ) : (
        <div className="whitespace-pre-wrap text-sm text-foreground">{draft}</div>
      )}
      <div className="mt-2 flex gap-2">
        {editing ? (
          <Button size="sm" onClick={() => onReject(rewrite.trim())} disabled={!rewrite.trim()}>
            改写后发送
          </Button>
        ) : (
          <>
            <Button size="sm" onClick={() => onApprove()}>
              直接发出
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setEditing(true)}>
              改写
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
