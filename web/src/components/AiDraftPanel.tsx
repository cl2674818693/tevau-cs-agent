import { useEffect, useState } from "react";

import { Button } from "./ui/button";

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
    <div className="rounded border border-line bg-fill-secondary p-3 mb-3">
      <div className="text-footnote text-ink-secondary mb-1">AI 草稿（未发送）</div>
      {editing ? (
        <textarea
          value={rewrite}
          onChange={(e) => setRewrite(e.target.value)}
          rows={4}
          className="w-full rounded border border-line px-3 py-2 text-body2 outline-none"
        />
      ) : (
        <div className="text-body2 text-ink-primary whitespace-pre-wrap">{draft}</div>
      )}
      <div className="flex gap-2 mt-2">
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
