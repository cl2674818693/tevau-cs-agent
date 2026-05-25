import * as React from "react";

import { cn } from "../../lib/utils";

export function Field({
  label,
  htmlFor,
  error,
  className,
  children,
}: {
  label?: string;
  htmlFor?: string;
  error?: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={cn("flex flex-col gap-1", className)}>
      {label && (
        <label htmlFor={htmlFor} className="text-body3 text-ink-subtle">
          {label}
        </label>
      )}
      {children}
      {error && <span className="text-body4 text-status-error">{error}</span>}
    </div>
  );
}
