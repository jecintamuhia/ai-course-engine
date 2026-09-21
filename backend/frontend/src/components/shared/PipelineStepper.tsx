import { Check, CircleDashed, Loader2, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { IngestionState } from "@/lib/types";
import {
  INGESTION_STEP_LABELS,
  INGESTION_STEP_ORDER,
  TERMINAL_STATES,
} from "@/lib/status";

interface PipelineStepperProps {
  jobStatus: IngestionState | null | undefined;
}

function stepState(
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

export function PipelineStepper({ jobStatus }: PipelineStepperProps) {
  const steps = INGESTION_STEP_ORDER.map((key, index) => {
    const state = stepState(index, jobStatus);
    const info = INGESTION_STEP_LABELS[key];
    const done = state === "done";
    const failed = state === "failed";
    const active = state === "active";

    return (
      <div
        key={key}
        className={cn(
          "flex items-center gap-2.5 rounded-full border px-3.5 py-2 text-xs font-semibold transition-colors",
          done && "border-emerald-200 bg-emerald-50 text-emerald-700",
          active && "border-oxford/40 bg-oxford-50 text-oxford-800",
          failed && "border-red-200 bg-red-50 text-red-700",
          state === "pending" && "border-border bg-card text-muted-foreground",
        )}
      >
        <StepIcon state={state} failed={failed} />
        <span>{info.title}</span>
        <span className="hidden font-normal opacity-70 sm:inline">— {info.description}</span>
      </div>
    );
  });

  const isPost = jobStatus && (TERMINAL_STATES.includes(jobStatus) || jobStatus === "completed");

  const terminal =
    jobStatus === "completed"
      ? {
          classes: "border-emerald-200 bg-emerald-50 text-emerald-700",
          iconClass: "text-emerald-700",
          label: "Dependencies & curriculum",
        }
      : jobStatus === "failed"
        ? {
            classes: "border-red-200 bg-red-50 text-red-700",
            iconClass: "text-red-700",
            label: "Pipeline failed",
          }
        : {
            classes: "border-border bg-card text-muted-foreground",
            iconClass: "text-muted-foreground",
            label: "Pipeline cancelled",
          };

  return (
    <div className="flex flex-wrap items-center gap-2.5">
      {steps}
      {isPost && (
        <div
          className={cn(
            "flex items-center gap-2.5 rounded-full border px-3.5 py-2 text-xs font-semibold",
            terminal.classes,
          )}
        >
          {jobStatus === "completed" ? (
            <Check className={cn("h-3.5 w-3.5", terminal.iconClass)} />
          ) : (
            <X className={cn("h-3.5 w-3.5", terminal.iconClass)} />
          )}
          <span>{terminal.label}</span>
        </div>
      )}
    </div>
  );
}

function StepIcon({ state, failed }: { state: string; failed: boolean }) {
  if (state === "done") return <Check className="h-3.5 w-3.5" />;
  if (failed) return <X className="h-3.5 w-3.5" />;
  if (state === "active") return <Loader2 className="h-3.5 w-3.5 animate-spin" />;
  return <CircleDashed className="h-3.5 w-3.5 opacity-50" />;
}