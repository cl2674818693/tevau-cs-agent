import { useState } from "react";

/** 消息内图片缩略图，点击全屏放大（点遮罩关闭）。 */
export function ImageThumb({ src }: { src: string }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <img
        src={src}
        alt="图片"
        onClick={() => setOpen(true)}
        className="max-h-48 max-w-[200px] cursor-zoom-in rounded-md object-cover"
      />
      {open && (
        <div
          onClick={() => setOpen(false)}
          className="fixed inset-0 z-50 grid place-items-center bg-black/80 p-4"
        >
          <img src={src} alt="" className="max-h-full max-w-full rounded" />
        </div>
      )}
    </>
  );
}
