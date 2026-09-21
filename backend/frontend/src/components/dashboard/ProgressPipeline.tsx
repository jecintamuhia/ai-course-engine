import { Link } from "react-router-dom";
import {
  BookOpen,
  BrainCircuit,
  CalendarRange,
  GraduationCap,
  ArrowRight,
  Upload,
} from "lucide-react";

import { cn } from "@/lib/utils";
import type { DashboardResponse } from "@/lib/types";

interface ProgressPipelineProps {
  stats: DashboardResponse;
  className?: string;
}

interface Stage {
  key: string;
  icon: typeof BookOpen;
  label: string;
  value: number | null;
  valueUnit: string;
  caption: string;
  to: string;
  active: boolean;
}

export function ProgressPipeline({ stats, className }: ProgressPipelineProps) {
  const stages: Stage[] = [
    {
      key: "textbook",
      icon: BookOpen,
      label: "Textbooks",
      value: stats.documents_total,
      valueUnit: stats.documents_total === 1 ? "document" : "documents",
      caption: "ingested into the library",
      to: "/documents",
      active: stats.documents_total > 0,
    },
    {
      key: "analysis",
      icon: BrainCircuit,
      label: "AI analysis",
      value: stats.documents_processing,
      valueUnit: stats.documents_processing === 1 ? "processing" : "processing",
      caption:
        stats.documents_processing > 0
          ? "documents being understood"
          : stats.documents_total > 0
            ? "no active jobs"
            : "waiting for a textbook",
      to: "/documents",
      active: stats.documents_processing > 0,
    },
    {
      key: "curriculum",
      icon: CalendarRange,
      label: "Curricula",
      value: stats.curricula_approved + stats.curricula_published,
      valueUnit: "approved",
      caption: "plans reviewed & approved by lecturers",
      to: "/courses",
      active: (stats.curricula_approved + stats.curricula_published) > 0,
    },
    {
      key: "moodle",
      icon: GraduationCap,
      label: "Moodle",
      value: stats.courses_published,
      valueUnit: stats.courses_published === 1 ? "course" : "courses",
      caption: "published and verified live",
      to: "/courses",
      active: stats.courses_published > 0,
    },
  ];

  const totalWithActivity = stages.reduce((acc, s) => acc + (s.active ? 1 : 0), 0);

  return (
    <section
      className={cn(
        "overflow-hidden rounded-2xl border border-border bg-card shadow-card",
        className,
      )}
    >
      <div className="relative p-5 sm:p-6">
        {/* faint brand wash */}
        <span
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-oxford/[0.05] to-transparent"
        />
        <div className="relative flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-oxford-700">
              Pipeline
            </p>
            <h2 className="mt-1 text-lg font-bold tracking-tight text-ink">
              Course intelligence pipeline
            </h2>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {totalWithActivity === 0
                ? "No activity yet — the pipeline starts the moment you upload a textbook."
                : `${totalWithActivity}/4 stages active — every number below is live backend data.`}
            </p>
          </div>
          <Link
            to="/upload"
            className="inline-flex items-center gap-2 rounded-md bg-oxford px-4 py-2 text-sm font-medium text-cream-50 shadow-sm transition-colors hover:bg-oxford-800"
          >
            <Upload className="h-4 w-4" />
            Upload textbook
          </Link>
        </div>
      </div>

      <ol className="relative grid grid-cols-1 gap-px bg-border sm:grid-cols-2 xl:grid-cols-4">
        {stages.map((stage, index) => {
          const Icon = stage.icon;
          return (
            <li key={stage.key} className="relative bg-card">
              <Link
                to={stage.to}
                className="group block h-full p-5 transition-colors hover:bg-cream-100/80"
              >
                <div className="flex items-center justify-between">
                  <span
                    className={cn(
                      "flex h-10 w-10 items-center justify-center rounded-xl ring-2 transition-colors",
                      stage.active
                        ? "bg-oxford-900 text-cream-50 ring-oxford-900/10"
                        : "bg-muted text-muted-foreground ring-border/60",
                    )}
                  >
                    <Icon className="h-5 w-5" />
                  </span>
                  <span className="text-[11px] font-bold tabular-nums text-muted-foreground/70">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                </div>

                <div className="mt-4">
                  <div className="flex items-baseline gap-1.5">
                    <span
                      className={cn(
                        "text-[28px] font-bold tracking-tight tabular-nums leading-none",
                        stage.active ? "text-ink" : "text-muted-foreground/70",
                      )}
                    >
                      {stage.value ?? "—"}
                    </span>
                    {stage.value != null && (
                      <span className="text-[11px] font-medium text-muted-foreground">
                        {stage.valueUnit}
                      </span>
                    )}
                  </div>
                  <div className="mt-1.5 text-[11px] font-semibold uppercase tracking-[0.1em] text-ink/80">
                    {stage.label}
                  </div>
                  <div className="mt-0.5 text-xs text-muted-foreground">{stage.caption}</div>
                </div>

                <div className="mt-4 flex items-center justify-between border-t border-border pt-3">
                  <span
                    className={cn(
                      "inline-flex items-center gap-1.5 text-[11px] font-semibold",
                      stage.active ? "text-emerald-700" : "text-muted-foreground",
                    )}
                  >
                    <span
                      aria-hidden
                      className={cn(
                        "h-1.5 w-1.5 rounded-full",
                        stage.active ? "bg-emerald-600" : "bg-muted-foreground/40",
                      )}
                    />
                    {stage.active ? "Active" : "Awaiting"}
                  </span>
                  <ArrowRight className="h-4 w-4 text-muted-foreground/60 transition-transform group-hover:translate-x-0.5 group-hover:text-oxford" />
                </div>
              </Link>
            </li>
          );
        })}
      </ol>
    </section>
  );
}