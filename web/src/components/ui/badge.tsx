import * as React from "react";

import { cn } from "../../lib/utils";

const variants = {
  neutral: "bg-surface-container text-ink-secondary",
  pending: "bg-status-warning/15 text-status-warning",
  takeover: "bg-brand-tab text-ink-onbrand",
  success: "bg-status-success/15 text-status-success",
  error: "bg-status-error/15 text-status-error",
} as const;

export function Badge({
  variant = "neutral",
  className,
  children,
}: {
  variant?: keyof typeof variants;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-sm px-2 py-0.5 text-body4",
        variants[variant],
        className,
      )}
    >
      {children}
    </span>
  );
}
