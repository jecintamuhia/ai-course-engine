import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Loader2,
  RotateCcw,
  Send,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Textarea } from "@/components/ui/textarea";
import { LearnerLoading } from "@/components/layout/LearnerShell";
import { SafeHtml } from "@/components/shared/SafeHtml";
import { api } from "@/lib/api";
import type { LearnerLessonRead } from "@/lib/types";

function BlockCard({
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
        {submission ? (
          <Badge
            variant={
              submission.status === "graded"
                ? "success"
                : submission.status === "needs_revision"
                ? "warning"
                : "info"
            }
          >
            {submission.status === "graded"
              ? "Graded"
              : submission.status === "needs_revision"
              ? "Revision requested"
              : "Awaiting review"}
          </Badge>
        ) : null}
      </div>

      {(prompt || instructions) && (
        <div className="mt-2 space-y-1 text-sm text-muted-foreground">
          {prompt && <p>{prompt}</p>}
          {instructions && <p className="text-[13px]">{instructions}</p>}
        </div>
      )}

      <Textarea
        className="mt-3 min-h-[140px] font-mono text-[13px]"
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
            <Send className="h-4 w-4" />
          )}
          {submission ? "Resubmit answer" : "Submit answer"}
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
 * A single lesson opened inside the learner portal.
 *
 * The actual lesson content is the Moodle Page activity published for this
 * lesson, fetched through the backend (read-only Moodle web service call)
 * and rendered in-portal. The learner is never sent to the Moodle
 * administration site. Completion is a separate, explicit action and the
 * lesson content can be read before it is marked complete.
 */
export function LearnerLessonPage() {
  const { courseId = "", lessonId = "" } = useParams();
  const [detail, setDetail] = useState<{
    course: { title: string; moodle_url: string | null };
    lessons: LearnerLessonRead[];
    progress: {
      total_lessons: number;
      completed_lessons: number;
      percentage: number;
    };
  } | null>(null);
  const [content, setContent] = useState<{
    title: string;
    content_html: string;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyLessonId, setBusyLessonId] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [courseDetail, lessonContent] = await Promise.all([
      api.learnerCourseDetail(courseId),
      api.learnerLessonContent(courseId, lessonId),
    ]);
    setDetail({
      course: courseDetail.course,
      lessons: courseDetail.lessons,
      progress: courseDetail.progress,
    });
    setContent({
      title: lessonContent.title,
      content_html: lessonContent.content_html,
    });
  }, [courseId, lessonId]);

  useEffect(() => {
    let active = true;
    load()
      .catch((cause: unknown) => {
        if (!active) return;
        setError(
          cause instanceof Error
            ? cause.message
            : "Could not open this lesson.",
        );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [load]);

  const lesson = detail?.lessons.find((item) => item.id === lessonId) ?? null;
  const lessonIndex = detail?.lessons.findIndex((item) => item.id === lessonId) ?? -1;
  const totalLessons = detail?.lessons.length ?? 0;

  const prevLesson = lessonIndex > 0 ? detail?.lessons[lessonIndex - 1] : null;
  const nextLesson =
    lessonIndex >= 0 && lessonIndex < totalLessons - 1
      ? detail?.lessons[lessonIndex + 1]
      : null;

  async function handleRetry() {
    setError(null);
    setLoading(true);
    try {
      await load();
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Could not open this lesson.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleToggleComplete() {
    if (!lesson) return;
    setBusyLessonId(lesson.id);
    setError(null);
    try {
      if (lesson.completed) {
        await api.learnerUncompleteLesson(courseId, lesson.id);
      } else {
        await api.learnerCompleteLesson(courseId, lesson.id);
      }
      const refreshed = await api.learnerCourseDetail(courseId);
      setDetail((current) =>
        current
          ? {
              ...current,
              lessons: current.lessons.map((item) =>
                item.id === lesson.id
                  ? { ...item, completed: !item.completed }
                  : item
              ),
              progress: refreshed.progress,
            }
          : current
      );
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Could not update your progress.",
      );
    } finally {
      setBusyLessonId(null);
    }
  }

  if (loading) return <LearnerLoading />;

  if (!detail || !content) {
    return (
      <div className="space-y-4">
        <p className="text-sm text-brand-800">
          {error || "This lesson could not be opened."}
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
          <Link to={`/learn/course/${courseId}`}>
            <ArrowLeft className="h-4 w-4" />
            Back to course
          </Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-7">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Button asChild variant="ghost" size="sm" className="-ml-2">
          <Link to={`/learn/course/${courseId}`}>
            <ArrowLeft className="h-4 w-4" />
            <span>Back to {detail.course.title}</span>
          </Link>
        </Button>
        <Progress
          className="relative z-10 mt-2 bg-navy-800"
          value={detail.progress.percentage}
          aria-label="Course progress"
        />
      </div>

      <section className="overflow-hidden rounded-2xl bg-navy-950 text-sand-100">
        <div className="relative px-6 py-8 sm:px-9">
          <div className="relative z-10 flex flex-wrap items-end justify-between gap-4">
            <div>
              <h1 className="font-display text-2xl font-bold text-white sm:text-3xl">
                {content.title}
              </h1>
              <p className="mt-1 text-sm text-sand-100/70">
                {detail.progress.completed_lessons} of{" "}
                {detail.progress.total_lessons} lessons complete.
              </p>
            </div>
          </div>
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

      <Card className="overflow-hidden">
        <CardHeader>
          <CardTitle className="font-display text-base text-navy-900">
            Lesson content
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <SafeHtml
            className="prose prose-sm max-w-none p-6 text-ink"
            html={content.content_html}
          />
        </CardContent>
      </Card>

      {lesson != null && lesson.blocks.some((block) => block.block_type === "practical_task") && (
        <section className="space-y-3">
          <h2 className="font-display text-lg font-bold text-navy-900">
            Practical tasks
          </h2>
          {lesson.blocks
            .filter((block) => block.block_type === "practical_task")
            .map((block) => (
              <BlockCard
                key={block.id}
                block={block}
                courseId={courseId}
                onSubmitted={() => void load()}
              />
            ))}
        </section>
      )}

      <div className="flex items-center justify-between gap-3 pt-4">
        <div className="flex items-center gap-2">
          {prevLesson && (
            <Button asChild size="sm" variant="outline">
              <Link to={`/learn/course/${courseId}/lesson/${prevLesson.id}`}>
                <ArrowLeft className="h-4 w-4" />
                <span>Previous lesson</span>
              </Link>
            </Button>
          )}
          {nextLesson && (
            <Button asChild size="sm" variant="default">
              <Link to={`/learn/course/${courseId}/lesson/${nextLesson.id}`}>
                <span>Next lesson</span>
                <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
          )}
        </div>
        <div className="flex items-center gap-3">
          {lesson != null && (
            <Button
              size="sm"
              variant={lesson.completed ? "outline" : "default"}
              disabled={busyLessonId === lesson.id}
              onClick={handleToggleComplete}
            >
              {busyLessonId === lesson.id ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : lesson.completed ? (
                <RotateCcw className="h-4 w-4" />
              ) : (
                <CheckCircle2 className="h-4 w-4" />
              )}
              {lesson.completed ? "Mark as not done" : "Mark as complete"}
            </Button>
          )}
          <p className="text-xs text-muted-foreground">
            Read the lesson content above before marking it complete.
          </p>
        </div>
      </div>
    </div>
  );
}
