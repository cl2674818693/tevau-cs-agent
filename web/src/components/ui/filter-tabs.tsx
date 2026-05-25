import { cn } from "../../lib/utils";

export function FilterTabs<T extends string>({
  value,
  onChange,
  options,
  className,
}: {
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: string }[];
  className?: string;
}) {
  return (
    <div className={cn("flex gap-2", className)}>
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            "rounded px-2 py-1 text-body3 transition-colors",
            value === o.value
              ? "bg-brand text-ink-onbrand"
              : "bg-surface-container text-ink-secondary hover:bg-surface-hover",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
