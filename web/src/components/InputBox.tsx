import { Send } from "lucide-react";
import {
  useEffect,
  useRef,
  useState,
  type ClipboardEvent,
  type KeyboardEvent,
} from "react";
import { useTranslation } from "react-i18next";

import { AttachButton } from "./AttachButton";

const MAX_IMAGES = 4;

export function InputBox({
  onSend,
  disabled,
  placeholder,
  upload,
}: {
  onSend: (t: string, attachmentIds?: number[]) => void;
  disabled: boolean;
  placeholder?: string;
  /** 上传一张图返回 attachment_id；未提供则不显示附件按钮。 */
  upload?: (file: File) => Promise<number>;
}) {
  const { t } = useTranslation();
  const [v, setV] = useState("");
  const [ids, setIds] = useState<number[]>([]);
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
    if ((text || ids.length) && !disabled) {
      onSend(text, ids);
      setV("");
      setIds([]);
    }
  }

  function onKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  async function onPaste(e: ClipboardEvent<HTMLTextAreaElement>) {
    if (!upload) return;
    const imgs = Array.from(e.clipboardData.files).filter((f) => f.type.startsWith("image/"));
    if (imgs.length === 0) return;
    e.preventDefault();
    let next = ids;
    for (const f of imgs.slice(0, MAX_IMAGES - ids.length)) {
      const id = await upload(f);
      next = [...next, id];
      setIds(next);
    }
  }

  const canSend = !disabled && (v.trim().length > 0 || ids.length > 0);

  return (
    <div className="border-t border-line bg-surface-card px-page py-block-sm safe-bottom">
      <div className="flex items-end gap-2 rounded-md bg-surface-page border border-line px-3 py-2 transition-all focus-within:border-brand focus-within:shadow-focus">
        {upload && (
          <AttachButton
            upload={upload}
            ids={ids}
            onChange={setIds}
            max={MAX_IMAGES}
            disabled={disabled}
          />
        )}
        <textarea
          ref={ref}
          value={v}
          rows={1}
          placeholder={placeholder ?? t("chat.inputPlaceholder")}
          onChange={(e) => setV(e.target.value)}
          onKeyDown={onKey}
          onPaste={onPaste}
          className="flex-1 resize-none bg-transparent text-body1 leading-6 text-ink placeholder:text-ink-placeholder outline-none max-h-32 overflow-y-auto scrollbar-hide py-0.5"
        />
        <button
          onClick={submit}
          disabled={!canSend}
          aria-label={t("chat.send")}
          className="grid h-10 w-10 place-items-center rounded bg-brand text-ink-onbrand transition-all hover:bg-brand-dark active:scale-90 disabled:opacity-40 disabled:bg-surface-disabled disabled:text-ink-placeholder"
        >
          <Send className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
