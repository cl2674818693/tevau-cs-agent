import { Send } from "lucide-react";
import { useState, type KeyboardEvent } from "react";

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
    <div className="border-t border-chat-primary/10 glass px-page py-block-sm safe-bottom">
      <div className="flex items-end gap-2 rounded-2xl bg-chat-surface-variant/50 border border-white/5 px-3 py-2 transition-all focus-within:border-chat-primary/50 focus-within:ring-1 focus-within:ring-chat-primary/20">
        <textarea
          value={v}
          rows={1}
          placeholder={placeholder}
          onChange={(e) => setV(e.target.value)}
          onKeyDown={onKey}
          className="flex-1 resize-none bg-transparent text-body1 text-chat-on-surface placeholder:text-chat-on-surface-variant/40 outline-none max-h-32"
        />
        <button
          onClick={submit}
          disabled={disabled || !v.trim()}
          aria-label="发送"
          className="grid h-10 w-10 place-items-center rounded-xl bg-chat-primary text-chat-on-primary transition-transform active:scale-90 disabled:opacity-50"
          style={{ boxShadow: "0 0 15px rgba(34,211,238,0.3)" }}
        >
          <Send className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
