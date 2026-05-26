import { ImagePlus, X } from "lucide-react";
import { useRef, useState } from "react";

type Pending = { id: number; url: string };

/** 受控选图组件：父持有已上传 ids，本组件管选图/上传/待发缩略图/删除。 */
export function AttachButton({
  upload,
  ids,
  onChange,
  max,
  disabled,
}: {
  upload: (file: File) => Promise<number>;
  ids: number[];
  onChange: (ids: number[]) => void;
  max: number;
  disabled?: boolean;
}) {
  const ref = useRef<HTMLInputElement>(null);
  const [pending, setPending] = useState<Pending[]>([]);
  const [busy, setBusy] = useState(false);

  async function pick(files: FileList | null) {
    if (!files) return;
    const room = max - ids.length;
    const chosen = Array.from(files).slice(0, room);
    setBusy(true);
    try {
      let next = ids;
      for (const f of chosen) {
        const id = await upload(f);
        next = [...next, id];
        setPending((p) => [...p, { id, url: URL.createObjectURL(f) }]);
        onChange(next);
      }
    } finally {
      setBusy(false);
      if (ref.current) ref.current.value = "";
    }
  }

  function remove(id: number) {
    setPending((p) => p.filter((x) => x.id !== id));
    onChange(ids.filter((x) => x !== id));
  }

  return (
    <>
      {pending.length > 0 && (
        <div className="flex gap-2 flex-wrap pb-2">
          {pending.map((p) => (
            <div key={p.id} className="relative">
              <img src={p.url} alt="" className="h-14 w-14 rounded object-cover" />
              <button
                type="button"
                onClick={() => remove(p.id)}
                className="absolute -right-1 -top-1 rounded-full bg-black/60 p-0.5 text-white"
                aria-label="remove"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          ))}
        </div>
      )}
      <button
        type="button"
        disabled={disabled || busy || ids.length >= max}
        onClick={() => ref.current?.click()}
        aria-label="attach image"
        className="grid h-10 w-10 place-items-center rounded text-ink-secondary hover:text-ink disabled:opacity-40"
      >
        <ImagePlus className="h-5 w-5" />
      </button>
      <input
        ref={ref}
        data-testid="attach-input"
        type="file"
        accept="image/*"
        multiple
        hidden
        onChange={(e) => void pick(e.target.files)}
      />
    </>
  );
}
