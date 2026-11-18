import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface MetricProps {
  value: string | number;
  label: string;
  accent?: "success" | "warning" | "danger" | "primary";
  icon?: ReactNode;
  className?: string;
}

const accentStyles: Record<string, string> = {
  success: "text-emerald-700",
  warning: "text-amber-600",
  danger: "text-red-600",
  primary: "text-brand",
};

export function Metric({ value, label, accent, icon, className }: MetricProps) {
  return (
    <div
      className={cn(
        "rounded-lg border border-border bg-card p-5 shadow-sm transition-shadow hover:shadow-md",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className={cn("text-3xl font-bold tracking-tight", accent && accentStyles[accent])}>
            {value}
          </div>
          <div className="mt-1.5 text-xs font-medium text-muted-foreground">{label}</div>
        </div>
        {icon && <div className="text-muted-foreground/60">{icon}</div>}
      </div>
    </div>
  );
}