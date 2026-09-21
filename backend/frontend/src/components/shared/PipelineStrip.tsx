import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, ChevronRight } from "lucide-react";

import { cn } from "@/lib/utils";

export type PipelineStageState = "active" | "pending" | "done";

export interface PipelineStage {
  key: string;
  label: string;
  state?: PipelineStageState;
  to?: string;
  icon?: ReactNode;
  detail?: ReactNode;
}

interface PipelineStripProps {
  stages: PipelineStage[];
  className?: string;
  /** Compact inline variant (chips with chevrons). */
  compact?: boolean;
}

const stateStyles: Record<PipelineStageState, string> = {
  done: "border-emerald-200 bg-emerald-50 text-emerald-800",
  active: "border-burgundy/25 bg-cream-200 text-burgundy-900",
  pending: "border-border bg-card text-muted-foreground",
};

/**
 * A product-narrative pipeline. Status is always computed from real data
 * by the caller — never hardcoded.
 */
export function PipelineStrip({ stages, className, compact = false }: PipelineStripProps) {
  return (
    <div className={cn("flex flex-wrap items-center gap-2", className)}>
      {stages.map((stage, index) => {
        const state = stage.state ?? "pending";
        const node = (
          <span
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[11px] font-semibold transition-colors",
              stateStyles[state],
              compact && "px-2.5 py-1",
            )}
          >
            {stage.icon}
            <span className="uppercase tracking-[0.08em]">{stage.label}</span>
            {state === "done" && <DoneDot />}
          </span>
        );
        return (
          <span key={stage.key} className="flex items-center gap-2">
            {stage.to && state !== "pending" ? (
              <Link
                to={stage.to}
                className="rounded-full transition-transform hover:scale-[1.02] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              >
                {node}
              </Link>
            ) : (
              node
            )}
            {index < stages.length - 1 &&
              (compact ? (
                <ChevronRight aria-hidden className="h-3.5 w-3.5 text-muted-foreground/50" />
              ) : (
                <ArrowRight aria-hidden className="h-3.5 w-3.5 shrink-0 text-muted-foreground/50" />
              ))}
          </span>
        );
      })}
    </div>
  );
}

function DoneDot() {
  return (
    <span aria-hidden className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-600" />
  );
}