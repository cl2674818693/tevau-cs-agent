import { useEffect, useRef, useState } from "react";

import { resolveAttachmentSrc } from "../api/attachments";

/**
 * 消息内图片缩略图：带鉴权取图片字节转 objectURL 再 <img> 显示，点击全屏放大（点遮罩关闭）。
 * 裸 <img> 直接用看图端点当 src 会 403（带不上鉴权头）。
 */
export function ImageThumb({
  src,
  resolve = resolveAttachmentSrc,
}: {
  /** 看图端点（/api/.../attachments/:id 或 /staff/...）。 */
  src: string;
  /** 端点 → 可显示 URL（objectURL）解析器。默认用户侧鉴权；客服侧传 token 版。 */
  resolve?: (endpoint: string) => Promise<string>;
}) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const [open, setOpen] = useState(false);
  // resolve 常是行内闭包（每 render 新建），用 ref 取最新，避免进 effect 依赖导致重复拉取
  const resolveRef = useRef(resolve);
  resolveRef.current = resolve;

  useEffect(() => {
    let alive = true;
    let created: string | null = null;
    setUrl(null);
    setFailed(false);
    resolveRef.current(src)
      .then((u) => {
        created = u;
        if (alive) setUrl(u);
        else URL.revokeObjectURL?.(u);
      })
      .catch(() => {
        if (alive) setFailed(true);
      });
    return () => {
      alive = false;
      if (created) URL.revokeObjectURL?.(created);
    };
  }, [src]);

  if (failed)
    return (
      <div className="grid h-20 w-28 place-items-center rounded-md bg-surface-subtle text-footnote text-ink-secondary">
        图片加载失败
      </div>
    );
  if (!url) return <div className="h-20 w-28 animate-pulse rounded-md bg-surface-subtle" />;

  return (
    <>
      <img
        src={url}
        alt="图片"
        onClick={() => setOpen(true)}
        className="max-h-48 max-w-[200px] cursor-zoom-in rounded-md object-cover"
      />
      {open && (
        <div
          onClick={() => setOpen(false)}
          className="fixed inset-0 z-50 grid place-items-center bg-black/80 p-4"
        >
          <img src={url} alt="" className="max-h-full max-w-full rounded" />
        </div>
      )}
    </>
  );
}
