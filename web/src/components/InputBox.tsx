import { Send } from "lucide-react";
import { useState, type KeyboardEvent } from "react";

import { Button } from "./ui/button";

export function InputBox({
  onSend,
  disabled,
  placeholder = "描述你的问题…",
}: {
  onSend: (t: string) => void;
  disabled: boolean;
  placeholder?: string;
}) {
  const [v, setV] = useState("");

  function submit() {
    const text = v.trim();
    if (text && !disabled) {
      onSend(text);
      setV("");
    }
  }

  function onKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <div className="border-t border-line bg-surface-card px-page py-block-sm safe-bottom">
      <div className="focus-glow flex items-end gap-2 rounded bg-white border border-line transition-all duration-250 px-3 py-2">
        <textarea
          value={v}
          rows={1}
          placeholder={placeholder}
          onChange={(e) => setV(e.target.value)}
          onKeyDown={onKey}
          className="flex-1 resize-none bg-transparent text-body1 placeholder:text-ink-secondary outline-none max-h-32"
        />
        <Button
          size="icon"
          onClick={submit}
          disabled={disabled || !v.trim()}
          aria-label="发送"
          className="h-9 w-9 rounded"
        >
          <Send className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
