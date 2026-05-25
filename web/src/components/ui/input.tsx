import * as React from "react";

import { cn } from "../../lib/utils";

const base =
  "focus-glow w-full rounded border border-line bg-surface-card px-input-x py-3 " +
  "text-body1 text-ink-primary outline-none transition-all duration-250 " +
  "placeholder:text-ink-secondary disabled:opacity-50";

export const Input = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(({ className, ...p }, ref) => <input ref={ref} className={cn(base, className)} {...p} />);
Input.displayName = "Input";

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...p }, ref) => (
  <textarea ref={ref} className={cn(base, "resize-none", className)} {...p} />
));
Textarea.displayName = "Textarea";
