import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, ExternalLink, Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { LearnerLoading } from "@/components/layout/LearnerShell";
import { api } from "@/lib/api";
import type {
  LearnerCourseDetailRead,
  LearnerLessonRead,
  MoodleCourseStructureRead,
  MoodleModuleRead,
} from "@/lib/types";

function submissionBadge(status: string) {
  if (status === "graded") return <Badge variant="success">Graded</Badge>;
  if (status === "needs_revision") {
    return <Badge variant="warning">Revision requested</Badge>;
  }
  return <Badge variant="info">Awaiting review</Badge>;
}

function PracticalTaskCard({
  block,
  courseId,
  onSubmitted,
}: {
  block: LearnerLessonRead["blocks"][number];
  courseId: string;
  onSubmitted: () => void;
}) {
  const [draft, setDraft] = useState(block.submission?.content ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const prompt =
    typeof block.payload.prompt === "string" ? block.payload.prompt : null;
  const instructions =
    typeof block.payload.instructions === "string"
      ? block.payload.instructions
      : null;

  async function handleSubmit() {
    if (!draft.trim()) {
      setError("Write your answer before submitting.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.learnerSubmitPractical(courseId, block.id, draft);
      onSubmitted();
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Could not submit your answer.",
      );
    } finally {
      setBusy(false);
    }
  }

  const submission = block.submission;

  return (
    <div className="rounded-xl border border-border bg-sand-50/60 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-semibold text-ink">
          {block.title || "Practical task"}
        </p>
        {submission ? submissionBadge(submission.status) : null}
      </div>

      {(prompt || instructions) && (
        <div className="mt-2 space-y-1 text-sm text-muted-foreground">
          {prompt && <p>{prompt}</p>}
          {instructions && <p className="text-[13px]">{instructions}</p>}
        </div>
      )}

      <textarea
        className="mt-3 min-h-[140px] font-mono text-[13px] border border-input rounded-lg bg-card p-2 text-ink focus:outline-none focus:ring-2 focus:ring-brand"
        placeholder="Write your answer in plain text or markdown…"
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        aria-label="Your answer"
      />

      {error && (
        <p className="mt-2 text-[13px] font-medium text-brand-700">{error}</p>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button size="sm" disabled={busy} onClick={handleSubmit}>
          {busy ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <span>Submit answer</span>
          )}
        </Button>
        {submission && (
          <span className="text-[12px] text-muted-foreground">
            Last submitted{" "}
            {new Date(submission.submitted_at).toLocaleString(undefined, {
              day: "numeric",
              month: "short",
              hour: "2-digit",
              minute: "2-digit",
            })}
          </span>
        )}
      </div>

      {submission?.feedback && (
        <div className="mt-3 rounded-lg border border-border bg-card px-3 py-2 text-[13px] text-ink">
          <p className="font-semibold text-navy-900">Lecturer feedback</p>
          <p className="mt-0.5 whitespace-pre-wrap text-muted-foreground">
            {submission.feedback}
          </p>
          {submission.grade !== null && (
            <p className="mt-1 text-[13px] font-semibold text-emerald-700">
              Mark: {submission.grade} / 100
            </p>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * A learner's view of one enrolled course.
 *
 * The curriculum (weeks, sections, lessons) is read from the Moodle course
 * this course record was published to. Lesson content opens inside the
 * portal at /learn/course/:courseId/lesson/:lessonId — the learner is never
 * sent to the Moodle administration site. The learner's own progress,
 * milestones and practical task hand-ins stay on this portal.
 */
export function LearnerCoursePage() {
  const { courseId = "" } = useParams();
  const navigate = useNavigate();
  const [detail, setDetail] = useState<LearnerCourseDetailRead | null>(null);
  const [structure, setStructure] = useState<MoodleCourseStructureRead | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [courseDetail, courseStructure] = await Promise.all([
      api.learnerCourseDetail(courseId),
      api.learnerCourseContent(courseId),
    ]);
    setDetail(courseDetail);
    setStructure(courseStructure);
  }, [courseId]);

  useEffect(() => {
    let active = true;

    load()
      .then((_) => {
        if (active) setLoading(false);
      })
      .catch((cause: unknown) => {
        if (!active) return;
        setError(
          cause instanceof Error
            ? cause.message
            : "Could not open this course.",
        );
        setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [load]);

  const lessonById = new Map<string, LearnerLessonRead>();
  detail?.lessons.forEach((lesson) => lessonById.set(lesson.id, lesson));

  async function handleRetry() {
    setError(null);
    setLoading(true);
    try {
      await load();
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Could not open this course.",
      );
    } finally {
      setLoading(false);
    }
  }

  if (loading) return <LearnerLoading />;

  if (!detail) {
    return (
      <div className="space-y-4">
        <p className="text-sm text-brand-800">
          {error || "This course could not be opened."}
        </p>
        {error && (
          <Button
            variant="outline"
            size="sm"
            onClick={handleRetry}
          >
            Try again
          </Button>
        )}
        <Button asChild variant="outline" size="sm">
          <Link to="/learn">
            <ArrowLeft className="h-4 w-4" />
            Back to your courses
          </Link>
        </Button>
      </div>
    );
  }

  const totalModules = structure
    ? structure.sections.reduce(
        (sum, section) =>
          sum + section.modules.filter((m) => m.modname === "page").length,
        0,
      )
    : 0;

  return (
    <div className="space-y-7">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Button asChild variant="ghost" size="sm" className="-ml-2">
          <Link to="/learn">
            <ArrowLeft className="h-4 w-4" />
            Your courses
          </Link>
        </Button>
        <Button variant="ghost" size="sm" onClick={() => navigate("/learn")}>
          Leave this course
        </Button>
      </div>

      <section className="overflow-hidden rounded-2xl bg-navy-950 text-sand-100">
        <div className="relative px-6 py-8 sm:px-9">
          <div className="relative z-10 flex flex-wrap items-end justify-between gap-4">
            <div className="max-w-2xl">
              <h1 className="font-display text-2xl font-bold text-white sm:text-3xl">
                {detail.course.title}
              </h1>
              <p className="mt-2 text-sm text-sand-100/70">
                {detail.progress.completed_lessons} of{" "}
                {detail.progress.total_lessons} lessons complete.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button asChild size="sm">
                <Link to={`/learn/course/${courseId}/assessment`}>
                  Final assessment
                </Link>
              </Button>
              {detail.course.moodle_url && (
                <Button asChild variant="outline" size="sm">
                  <a
                    href={detail.course.moodle_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <span className="flex items-center gap-1">
                      View on Moodle
                      <ExternalLink className="h-3.5 w-3.5" />
                    </span>
                  </a>
                </Button>
              )}
            </div>
          </div>
          <Progress
            className="relative z-10 mt-5 bg-navy-800"
            value={detail.progress.percentage}
            aria-label="Course progress"
          />
        </div>
      </section>

      {error && (
        <div className="rounded-lg border border-brand/30 bg-brand/5 px-4 py-3 text-sm text-brand-800">
          {error}
          <Button
            variant="outline"
            size="sm"
            className="ml-4"
            onClick={handleRetry}
          >
            Try again
          </Button>
        </div>
      )}

      {structure ? (
        <>
          {structure.sections.map((section) => (
            <section key={section.section_number} className="space-y-3">
              <h2 className="font-display text-lg font-bold text-navy-900">
                Week {section.section_number}
              </h2>
              <p className="text-sm text-muted-foreground">
                {section.name}
              </p>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {section.modules
                  .filter((module) => module.modname === "page")
                  .map((module) => {
                    const lesson = module.lesson_id
                      ? lessonById.get(module.lesson_id)
                      : undefined;
                    return (
                      <LessonCard
                        key={module.cmid}
                        module={module}
                        lesson={lesson ?? null}
                        courseId={courseId}
                      />
                    );
                  })}
              </div>
              {section.modules.filter((module) => module.modname === "page")
                .length === 0 && (
                <Card>
                  <CardContent className="py-8 text-center text-sm text-muted-foreground">
                    No lessons published in this week yet.
                  </CardContent>
                </Card>
              )}
            </section>
          ))}
          {totalModules === 0 && (
            <Card>
              <CardContent className="py-10 text-center text-sm text-muted-foreground">
                No lessons have been published for this course yet. Ask your
                lecturer to publish the course content to Moodle.
              </CardContent>
            </Card>
          )}
        </>
      ) : null}

      {!structure && !error && detail.lessons.length === 0 && (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            No lessons have been published for this course yet.
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function LessonCard({
  module,
  lesson,
  courseId,
}: {
  module: MoodleModuleRead;
  lesson: LearnerLessonRead | null;
  courseId: string;
}) {
  const completed = lesson?.completed ?? false;
  const objectives = lesson?.learning_objectives.length ?? 0;

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <CardTitle className="font-display text-base text-navy-900">
              {module.name || "Lesson"}
            </CardTitle>
            <CardDescription className="mt-1">
              {lesson?.description ?? ""}
              {objectives > 0 && (
                <span className="ml-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                  {objectives} objective{objectives === 1 ? "" : "s"}
                </span>
              )}
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            {completed ? "Completed" : "Not started"}
          </p>
          {lesson ? (
            <Button asChild size="sm" variant="default">
              <Link to={`/learn/course/${courseId}/lesson/${lesson.id}`}>
                Open lesson
              </Link>
            </Button>
          ) : (
            <Button size="sm" variant="outline" disabled>
              Content not available
            </Button>
          )}
        </div>
        {lesson != null && (
          <div className="mt-2 space-y-2">
            {lesson.blocks
              .filter((block) => block.block_type === "practical_task")
              .map((block) => (
                <PracticalTaskCard
                  key={block.id}
                  block={block}
                  courseId={courseId}
                  onSubmitted={() => {}}
                />
              ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
