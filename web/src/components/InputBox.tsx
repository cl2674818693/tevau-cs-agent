import { Send } from "lucide-react";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";

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
  const ref = useRef<HTMLTextAreaElement>(null);

  // 自动撑高：内容多行时跟随增高，最高 max-h-32 后内部滚动
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [v]);

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
      <div className="flex items-center gap-2 rounded-md bg-surface-page border border-line px-3 py-2 transition-all focus-within:border-brand focus-within:shadow-focus">
        <textarea
          ref={ref}
          value={v}
          rows={1}
          placeholder={placeholder}
          onChange={(e) => setV(e.target.value)}
          onKeyDown={onKey}
          className="flex-1 resize-none bg-transparent text-body1 leading-6 text-ink placeholder:text-ink-placeholder outline-none max-h-32 overflow-y-auto scrollbar-hide py-0.5"
        />
        <button
          onClick={submit}
          disabled={disabled || !v.trim()}
          aria-label="发送"
          className="grid h-10 w-10 place-items-center rounded bg-brand text-ink-onbrand transition-all hover:bg-brand-dark active:scale-90 disabled:opacity-40 disabled:bg-surface-disabled disabled:text-ink-placeholder"
        >
          <Send className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
