import * as React from "react";

import { cn } from "../../lib/utils";

const variants = {
  info: "bg-surface-container text-ink-secondary",
  success: "bg-status-success/10 text-status-success",
  error: "bg-status-error/10 text-status-error",
} as const;

export function Alert({
  variant = "info",
  className,
  children,
}: {
  variant?: keyof typeof variants;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={cn("rounded px-3 py-2 text-body3", variants[variant], className)}>
      {children}
    </div>
  );
}
