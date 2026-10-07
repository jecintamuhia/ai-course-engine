import { useCallback, useEffect, useRef, useState } from "react";
import { BookOpenCheck, Loader2, Play, RotateCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { api } from "@/lib/api";
import type { ContentGenerationJob, CurriculumDetailRead } from "@/lib/types";
import { toast } from "sonner";
import type { Tone } from "@/lib/status";

interface BulkGenerationPanelProps {
  curriculum: CurriculumDetailRead;
  onUpdated: () => void;
}

const POLL_INTERVAL_MS = 5000;

const STATUS_TONES: Record<string, Tone> = {
  pending: "neutral",
  running: "warning",
  completed: "success",
  failed: "danger",
  cancelled: "neutral",
};

const STATUS_LABELS: Record<string, string> = {
  pending: "queued",
  running: "generating",
  completed: "complete",
  failed: "failed",
  cancelled: "cancelled",
};

const ACTIVE: ContentGenerationJob["status"][] = ["pending", "running"];

export function BulkGenerationPanel({
  curriculum,
  onUpdated,
}: BulkGenerationPanelProps) {
  const [job, setJob] = useState<ContentGenerationJob | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const notifiedFor = useRef<string | null>(null);

  const isActive = job !== null && ACTIVE.includes(job.status);

  const load = useCallback(async () => {
    try {
      setJob(await api.getContentGenerationJob(curriculum.id));
    } catch {
      setJob(null);
    }
  }, [curriculum.id]);

  useEffect(() => {
    void load();
  }, [load]);

  // Poll only while a run is in flight, then refresh the curriculum so
  // lesson counts elsewhere on the page reflect what was generated.
  useEffect(() => {
    if (!isActive) {
      if (job && notifiedFor.current !== job.id) {
        notifiedFor.current = job.id;
        if (job.status === "completed") {
          toast.success(
            `Generated ${job.lessons_generated} lessons across ${job.completed_weeks} weeks.`,
          );
          onUpdated();
        } else if (job.status === "failed") {
          toast.error(job.error_message ?? "Lesson generation failed.");
        }
      }
      return;
    }

    const timer = window.setInterval(() => {
      void load();
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
    // onUpdated is stable enough for this effect; job.id gates the toast so
    // completion is announced exactly once per run.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isActive, job?.id, job?.status, load]);

  const start = async (withRebuild: boolean) => {
    setSubmitting(true);
    try {
      const response = await api.generateAllLessons(curriculum.id, withRebuild);
      setJob(response.job);
      notifiedFor.current = null;
      toast.success(
        response.created
          ? "Queued lesson generation for the whole course."
          : "A generation run is already in progress.",
      );
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  const percent =
    job && job.total_weeks > 0
      ? Math.round((job.completed_weeks / job.total_weeks) * 100)
      : 0;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <BookOpenCheck className="h-4 w-4 text-ai" /> Course Lessons
        </CardTitle>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="default"
            onClick={() => void start(false)}
            disabled={submitting || isActive || curriculum.status !== "approved"}
          >
            {isActive ? (
              <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
            ) : (
              <Play className="mr-1 h-3.5 w-3.5" />
            )}
            {isActive ? "Generating…" : "Generate missing weeks"}
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => void start(true)}
            disabled={submitting || isActive || curriculum.status !== "approved"}
            title="Regenerate every week, including ones that already have lessons"
          >
            <RotateCcw className="mr-1 h-3.5 w-3.5" />
            Rebuild all
          </Button>
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        {curriculum.status !== "approved" ? (
          <p className="text-xs text-muted-foreground">
            Approve this curriculum before generating its lessons.
          </p>
        ) : job === null ? (
          <p className="text-xs text-muted-foreground">
            No lessons generated for the whole course yet. Generating the
            remaining weeks writes full lessons grounded in the textbook
            chunks, and can take a while — it runs in the background and
            existing lessons are never touched.
          </p>
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-3">
              <StatusBadge
                tone={STATUS_TONES[job.status] ?? "neutral"}
                label={STATUS_LABELS[job.status] ?? job.status}
              />
              <span className="text-xs text-muted-foreground">
                {job.completed_weeks}/{job.total_weeks} weeks ·{" "}
                {job.lessons_generated} lessons generated
                {job.skipped_weeks > 0 && ` · ${job.skipped_weeks} already had lessons`}
                {job.failed_weeks > 0 &&
                  ` · ${job.failed_weeks} produced no lessons`}
              </span>
            </div>

            <div
              className="h-2 w-full overflow-hidden rounded-full bg-muted"
              role="progressbar"
              aria-valuenow={percent}
              aria-valuemin={0}
              aria-valuemax={100}
            >
              <div
                className="h-full rounded-full bg-ai transition-all duration-500"
                style={{ width: `${percent}%` }}
              />
            </div>

            {job.status === "failed" && job.error_message && (
              <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">
                {job.error_message}
              </p>
            )}

            {job.status === "running" && (
              <p className="text-xs text-muted-foreground">
                This runs in the background. Weeks that already have lessons are
                skipped, so it is safe to leave this page.
              </p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
