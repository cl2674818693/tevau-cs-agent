import { Image as AntImage, Skeleton } from "antd";
import { useEffect, useState } from "react";

import { resolveStaffAttachmentSrc } from "../api/attachments";

type Props = {
  /** 看图端点（/staff/api/v1/.../attachments/:id），由调用方通过 staffAttachmentUrl 拼好。 */
  src: string;
  token: string;
  size?: number;
};

/**
 * 客服/管理后台图片缩略图：用 Bearer 取图片字节转 objectURL，再交给 antd Image
 * 渲染，原生自带缩放/旋转/下载预览工具栏。客服侧专用——不能直接用 H5 版的
 * ImageThumb，那是用户鉴权解析器，admin 没 user token 会被 403。
 */
export function StaffImageThumb({ src, token, size = 96 }: Props) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    let created: string | null = null;
    setUrl(null);
    setFailed(false);
    resolveStaffAttachmentSrc(src, token)
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
  }, [src, token]);

  if (failed) {
    return (
      <div
        style={{
          width: size,
          height: size,
          display: "grid",
          placeItems: "center",
          borderRadius: 6,
          background: "rgba(0,0,0,0.04)",
          color: "rgba(0,0,0,0.45)",
          fontSize: 12,
        }}
      >
        图片加载失败
      </div>
    );
  }

  if (!url) {
    return <Skeleton.Image active style={{ width: size, height: size }} />;
  }

  return (
    <AntImage
      src={url}
      width={size}
      height={size}
      style={{ borderRadius: 6, objectFit: "cover" }}
      preview={{ mask: "预览" }}
    />
  );
}
