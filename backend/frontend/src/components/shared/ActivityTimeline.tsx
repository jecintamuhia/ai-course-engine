import type { ReactNode } from "react";

import { formatDate, formatTime } from "@/lib/format";
import { cn } from "@/lib/utils";

export type ActivityTone = "primary" | "success" | "warning" | "danger" | "neutral" | "ai";

export interface ActivityItem {
  id: string;
  title: string;
  description?: string;
  timestamp?: string | null;
  icon: ReactNode;
  tone?: ActivityTone;
}

const dotStyles: Record<ActivityTone, { dot: string; ring: string }> = {
  primary: { dot: "bg-burgundy", ring: "ring-burgundy/15" },
  success: { dot: "bg-emerald-500", ring: "ring-emerald-500/15" },
  warning: { dot: "bg-amber-500", ring: "ring-amber-500/15" },
  danger: { dot: "bg-red-500", ring: "ring-red-500/15" },
  neutral: { dot: "bg-cream-300", ring: "ring-cream-300/30" },
  ai: { dot: "bg-ai/70", ring: "ring-ai/15" },
};

interface ActivityTimelineProps {
  items: ActivityItem[];
  className?: string;
}

export function ActivityTimeline({ items, className }: ActivityTimelineProps) {
  if (items.length === 0) return null;
  return (
    <ol className={cn("relative space-y-0", className)}>
      {items.map((item, index) => {
        const style = dotStyles[item.tone ?? "neutral"];
        const isLast = index === items.length - 1;
        return (
          <li key={item.id} className="relative flex gap-3.5 pb-5 last:pb-0">
            {!isLast && (
              <span
                aria-hidden
                className="absolute left-[13px] top-8 h-[calc(100%-20px)] w-px bg-border"
              />
            )}
            <span
              aria-hidden
              className={cn(
                "mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full ring-4",
                style.dot,
                style.ring,
              )}
            >
              <span className="text-[11px] text-white/90">{item.icon}</span>
            </span>
            <div className="min-w-0 flex-1 pt-0.5">
              <div className="flex items-baseline justify-between gap-3">
                <p className="truncate text-sm font-medium text-ink">{item.title}</p>
                {item.timestamp && (
                  <time
                    className="shrink-0 text-[11px] tabular-nums text-muted-foreground"
                    dateTime={item.timestamp}
                  >
                    {formatTime(item.timestamp)} · {formatDate(item.timestamp)}
                  </time>
                )}
              </div>
              {item.description && (
                <p className="mt-0.5 line-clamp-2 text-xs leading-relaxed text-muted-foreground">
                  {item.description}
                </p>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}