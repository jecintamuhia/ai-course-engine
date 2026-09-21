import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight } from "lucide-react";

import { cn } from "@/lib/utils";

type MetricTone = "neutral" | "primary" | "success" | "warning" | "danger" | "ai";

interface MetricCardProps {
  label: string;
  value: ReactNode;
  icon?: ReactNode;
  tone?: MetricTone;
  context?: ReactNode;
  to?: string;
  className?: string;
}

const toneStyles: Record<MetricTone, { accent: string; chip: string; value: string }> = {
  neutral: {
    accent: "bg-cream-300",
    chip: "bg-muted text-muted-foreground",
    value: "text-ink",
  },
  primary: {
    accent: "bg-oxford",
    chip: "bg-oxford-50 text-oxford",
    value: "text-ink",
  },
  success: {
    accent: "bg-emerald-500",
    chip: "bg-emerald-50 text-emerald-700",
    value: "text-ink",
  },
  warning: {
    accent: "bg-amber-500",
    chip: "bg-amber-50 text-amber-700",
    value: "text-ink",
  },
  danger: {
    accent: "bg-red-500",
    chip: "bg-red-50 text-red-700",
    value: "text-ink",
  },
  ai: {
    accent: "bg-ai/60",
    chip: "bg-ai/10 text-ai",
    value: "text-ink",
  },
};

export function MetricCard({
  label,
  value,
  icon,
  tone = "neutral",
  context,
  to,
  className,
}: MetricCardProps) {
  const style = toneStyles[tone];
  const body = (
    <>
      <span
        aria-hidden
        className={cn("absolute inset-x-4 top-0 h-0.5 rounded-b", style.accent)}
      />
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
            {label}
          </div>
          <div
            className={cn(
              "mt-1.5 text-3xl font-bold tracking-tight tabular-nums",
              style.value,
            )}
          >
            {value}
          </div>
        </div>
        {icon && (
          <span
            className={cn(
              "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg",
              style.chip,
            )}
          >
            {icon}
          </span>
        )}
      </div>
      {context && (
        <div className="mt-4 flex items-center gap-1.5 border-t border-border pt-2.5 text-xs text-muted-foreground">
          {context}
        </div>
      )}
    </>
  );

  const classes = cn(
    "group relative overflow-hidden rounded-xl border border-border bg-card p-5 shadow-card transition-all",
    to && "hover:-translate-y-0.5 hover:border-oxford/25 hover:shadow-lift",
    className,
  );

  if (to) {
    return (
      <Link to={to} className={classes}>
        {body}
        <ArrowUpRight className="absolute right-4 top-4 h-4 w-4 text-muted-foreground/50 transition-colors group-hover:text-oxford" />
      </Link>
    );
  }
  return <div className={classes}>{body}</div>;
}