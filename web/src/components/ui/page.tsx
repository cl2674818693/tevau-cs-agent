import * as React from "react";

import { cn } from "../../lib/utils";

const widths = {
  default: "max-w-[720px]",
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
        "mx-auto px-page py-block-lg",
        widths[width],
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
