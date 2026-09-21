import type { ReactNode } from "react";
import { Sparkles } from "lucide-react";

import { cn } from "@/lib/utils";

interface AIInsightProps {
  children: ReactNode;
  title?: string;
  icon?: ReactNode;
  className?: string;
}

/**
 * A restrained "AI insight" callout. The indigo accent is used here
 * deliberately and sparingly to signal machine-generated observation.
 */
export function AIInsight({ children, title = "AI insight", icon, className }: AIInsightProps) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-xl border border-ai/15 bg-card p-4",
        className,
      )}
    >
      <span
        aria-hidden
        className="pointer-events-none absolute right-3 top-3 h-16 w-16 rounded-full bg-ai/[0.06] blur-2xl"
      />
      <div className="relative flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-ai">
        {icon ?? <Sparkles className="h-3.5 w-3.5" />}
        {title}
      </div>
      <div className="relative mt-2.5 text-sm leading-relaxed text-ink/90">{children}</div>
    </div>
  );
}