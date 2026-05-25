import * as React from "react";

import { cn } from "../../lib/utils";

export function EmptyState({
  className,
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={cn("py-8 text-center text-body3 text-ink-secondary", className)}>
      {children}
    </div>
  );
}
