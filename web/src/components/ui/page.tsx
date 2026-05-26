import * as React from "react";

import { cn } from "../../lib/utils";

const widths = {
  wide: "max-w-[1040px]",
  default: "max-w-[840px]",
  form: "max-w-[560px]",
  narrow: "max-w-[420px]",
} as const;

export function PageContainer({
  width = "default",
  center = false,
  fullHeight = false,
  className,
  children,
}: {
  width?: keyof typeof widths;
  center?: boolean;
  fullHeight?: boolean;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        // 移动端全宽 + 16px 内边距；桌面端更大留白。
        "px-page py-block-lg md:px-8 md:py-7",
        widths[width],
        // 登录等独立页水平+垂直居中；后台内容页左对齐贴侧栏，不再飘在宽屏正中。
        center ? "mx-auto" : "",
        (center || fullHeight) && "flex h-full flex-col",
        center && "justify-center",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function PageHeader({
  title,
  actions,
  className,
}: {
  title: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("mb-3 flex items-center gap-2", className)}>
      <h2 className="flex-1 text-sh2 text-ink-primary">{title}</h2>
      {actions}
    </div>
  );
}
