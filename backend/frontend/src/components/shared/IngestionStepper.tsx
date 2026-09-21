import { Check, CircleDashed, Loader2, X } from "lucide-react";
import { Link } from "react-router-dom";

import { cn } from "@/lib/utils";
import type { IngestionState } from "@/lib/types";
import {
  INGESTION_STEP_LABELS,
  INGESTION_STEP_ORDER,
  TERMINAL_STATES,
} from "@/lib/status";

interface TrailingStage {
  key: string;
  label: string;
  detail?: string;
  state: "done" | "active" | "pending";
  to?: string;
}

interface IngestionStepperProps {
  jobStatus: IngestionState | null | undefined;
  /** Optional post-processing stages (curriculum → review → publish). */
  trailing?: TrailingStage[];
  className?: string;
}

function stageState(
  index: number,
  jobStatus: IngestionState | null | undefined,
): "done" | "active" | "failed" | "pending" {
  if (!jobStatus) return "pending";
  if (jobStatus === "completed") return "done";
  const currentIndex = INGESTION_STEP_ORDER.indexOf(
    jobStatus as (typeof INGESTION_STEP_ORDER)[number],
  );
  const failed = jobStatus === "failed";
  const cancelled = jobStatus === "cancelled";
  if (failed || cancelled) {
    if (index < currentIndex) return "done";
    if (index === currentIndex) return "failed";
    return "pending";
  }
  if (index < currentIndex) return "done";
  if (index === currentIndex) return "active";
  return "pending";
}

const finished =
  (jobStatus: IngestionState | null | undefined) =>
  (s: TrailingStage): "done" | "active" | "pending" | "failed" => {
    if (!jobStatus || !TERMINAL_STATES.includes(jobStatus)) return "pending";
    if (jobStatus !== "completed") return "pending";
    return s.state;
  };

export function IngestionStepper({
  jobStatus,
  trailing,
  className,
}: IngestionStepperProps) {
  const computeTrailing = finished(jobStatus);
  const allStages: Array<{ key: string; state: ReturnType<typeof stageState>; node: React.ReactNode }> =
    INGESTION_STEP_ORDER.map((key, index) => ({
      key,
      state: stageState(index, jobStatus),
      node: (
        <div
          key={key}
          className="flex items-center justify-between gap-3 text-[13px] leading-snug py-2"
        >
          <div className="min-w-0">
            <div className="font-medium text-ink">{INGESTION_STEP_LABELS[key].title}</div>
            <div className="truncate text-[11px] text-muted-foreground">
              {INGESTION_STEP_LABELS[key].description}
            </div>
          </div>
          <StateIcon state={stageState(index, jobStatus)} />
        </div>
      ),
    }));

  const trailingNodes: typeof allStages =
    trailing?.map((t) => ({
      key: t.key,
      state: computeTrailing(t),
      node: (
        <div
          key={t.key}
          className="flex items-center justify-between gap-3 text-[13px] leading-snug py-2"
        >
          <div className="min-w-0">
            <div className="font-medium text-ink">{t.label}</div>
            {t.detail && <div className="truncate text-[11px] text-muted-foreground">{t.detail}</div>}
          </div>
          {t.to && t.state !== "pending" ? (
            <Link
              to={t.to}
              className="text-[11px] font-semibold text-burgundy-700 hover:text-burgundy-800"
            >
              Open
            </Link>
          ) : (
            <StateIcon state={computeTrailing(t)} />
          )}
        </div>
      ),
    })) ?? [];

  const combined = [...allStages, ...trailingNodes];
  if (combined.length === 0) return null;

  return (
    <ol className={cn("relative", className)}>
      {combined.map(({ key, state, node }, index) => {
        const isLast = index === combined.length - 1;
        return (
          <li key={key} className="relative flex gap-3.5">
            <div className="flex flex-col items-center">
              <NodeDot state={state} />
              {!isLast && (
                <span
                  aria-hidden
                  className={cn(
                    "w-px flex-1",
                    state === "done" ? "bg-emerald-300" : "bg-border",
                  )}
                />
              )}
            </div>
            <div className={cn("min-w-0 flex-1", !isLast && "mb-1.5")}>{node}</div>
          </li>
        );
      })}
    </ol>
  );
}

function NodeDot({ state }: { state: "done" | "active" | "failed" | "pending" }) {
  return (
    <span
      aria-hidden
      className={cn(
        "mt-2 flex h-6 w-6 shrink-0 items-center justify-center rounded-full ring-4",
        state === "done" && "bg-emerald-100 text-emerald-700 ring-emerald-500/10",
        state === "active" && "bg-burgundy-900 text-cream-50 ring-burgundy/10 animate-pulse-soft",
        state === "failed" && "bg-red-100 text-red-700 ring-red-500/10",
        state === "pending" && "bg-muted text-muted-foreground/70 ring-border/50",
      )}
    >
      {state === "done" && <Check className="h-3.5 w-3.5" />}
      {state === "active" && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
      {state === "failed" && <X className="h-3.5 w-3.5" />}
      {state === "pending" && <CircleDashed className="h-3.5 w-3.5" />}
    </span>
  );
}

function StateIcon({
  state,
}: {
  state: "done" | "active" | "failed" | "pending";
}) {
  if (state === "done") return <Check className="h-4 w-4 text-emerald-600" />;
  if (state === "active") return <Loader2 className="h-4 w-4 animate-spin text-burgundy" />;
  if (state === "failed") return <X className="h-4 w-4 text-red-600" />;
  return <CircleDashed className="h-4 w-4 text-muted-foreground/50" />;
}