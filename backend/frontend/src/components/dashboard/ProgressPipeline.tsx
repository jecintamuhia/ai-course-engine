import { Link } from "react-router-dom";
import {
  BookOpen,
  BrainCircuit,
  CalendarRange,
  GraduationCap,
  ArrowRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { DashboardResponse } from "@/lib/types";

interface ProgressPipelineProps {
  stats: DashboardResponse;
  className?: string;
}

interface Stage {
  key: "textbook" | "intelligence" | "curriculum" | "moodle";
  icon: typeof BookOpen;
  label: string;
  value: number;
  valueLabel: string;
  to?: string;
}

export function ProgressPipeline({ stats, className }: ProgressPipelineProps) {
  const stages: Stage[] = [
    {
      key: "textbook",
      icon: BookOpen,
      label: "Textbook",
      value: stats.documents_total,
      valueLabel: "documents ingested",
      to: "/documents",
    },
    {
      key: "intelligence",
      icon: BrainCircuit,
      label: "AI understanding",
      value: stats.curricula_total > 0 ? stats.curricula_total : stats.documents_processing,
      valueLabel: stats.curricula_total > 0 ? "analyses ready" : "processing now",
      to: "/dashboard",
    },
    {
      key: "curriculum",
      icon: CalendarRange,
      label: "Curriculum",
      value: stats.curricula_approved + stats.curricula_published,
      valueLabel: "approved plans",
      to: "/dashboard",
    },
    {
      key: "moodle",
      icon: GraduationCap,
      label: "Moodle",
      value: stats.courses_published,
      valueLabel: "courses live",
      to: "/courses",
    },
  ];

  const completedCount = stages.reduce(
    (acc, stage) => acc + (stage.value > 0 ? 1 : 0),
    0,
  );

  return (
    <section
      className={cn(
        "rounded-2xl border border-border bg-card",
        className,
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-5 py-4">
        <div>
          <h3 className="text-sm font-semibold text-foreground">
            Textbook &rarr; Moodle pipeline
          </h3>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {completedCount === 4
              ? "All four stages are active — your publishing pipeline is live."
              : `${completedCount}/4 stages with activity — everything shown is real backend data.`}
          </p>
        </div>
        <Link
          to="/upload"
          className="inline-flex items-center gap-1 text-xs font-semibold text-burgundy-700 hover:text-burgundy-800"
        >
          Upload a textbook <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </div>

      <ol className="grid grid-cols-1 gap-3 p-5 sm:grid-cols-2 xl:grid-cols-4">
        {stages.map((stage, index) => {
          const Icon = stage.icon;
          const active = stage.value > 0;
          const node = (
            <div
              className={cn(
                "relative flex h-full flex-col gap-3 rounded-xl border p-4 transition-colors",
                active
                  ? "border-burgundy/25 bg-burgundy-50/50 hover:border-burgundy/40"
                  : "border-border bg-muted/30",
              )}
            >
              <div className="flex items-center justify-between">
                <span
                  className={cn(
                    "flex h-9 w-9 items-center justify-center rounded-lg",
                    active ? "bg-burgundy text-cream-50" : "bg-muted text-muted-foreground",
                  )}
                >
                  <Icon className="h-4 w-4" />
                </span>
                <span className="text-[10px] font-semibold tabular-nums text-muted-foreground">
                  {String(index + 1).padStart(2, "0")}
                </span>
              </div>
              <div>
                <div
                  className={cn(
                    "text-2xl font-bold tracking-tight tabular-nums",
                    active ? "text-foreground" : "text-muted-foreground",
                  )}
                >
                  {stage.value}
                </div>
                <div className="mt-0.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                  {stage.label}
                </div>
                <div className="mt-0.5 text-xs text-muted-foreground">{stage.valueLabel}</div>
              </div>
            </div>
          );

          return (
            <li key={stage.key} className="relative">
              {index < stages.length - 1 && (
                <ArrowRight
                  aria-hidden
                  className="absolute -right-[13px] top-1/2 z-10 hidden h-4 w-4 -translate-y-6 text-border xl:block"
                />
              )}
              {stage.to && active ? (
                <Link to={stage.to} className="block h-full transition-opacity hover:opacity-90">
                  {node}
                </Link>
              ) : (
                node
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}