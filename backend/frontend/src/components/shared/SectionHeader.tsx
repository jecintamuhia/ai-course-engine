import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface SectionHeaderProps {
  title: string;
  description?: string;
  icon?: ReactNode;
  action?: ReactNode;
  hint?: ReactNode;
  className?: string;
}

/**
 * A consistent section title row used inside cards and panels.
 */
export function SectionHeader({
  title,
  description,
  icon,
  action,
  hint,
  className,
}: SectionHeaderProps) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-start justify-between gap-x-6 gap-y-2",
        className,
      )}
    >
      <div className="flex min-w-0 items-start gap-2.5">
        {icon && (
          <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-burgundy-50 text-burgundy">
            {icon}
          </span>
        )}
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-ink">{title}</h3>
            {hint && (
              <span className="truncate text-xs text-muted-foreground">{hint}</span>
            )}
          </div>
          {description && (
            <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
              {description}
            </p>
          )}
        </div>
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}