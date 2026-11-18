import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  CheckCircle2,
  Loader2,
  MessageSquare,
  RotateCcw,
  Users,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import type {
  LecturerActivityRead,
  LecturerLearnerProgress,
  MoodleCourseRead,
  PracticalSubmissionRead,
} from "@/lib/types";

function statusBadge(status: string) {
  if (status === "graded") return <Badge variant="success">Graded</Badge>;
  if (status === "needs_revision") {
    return <Badge variant="warning">Revision requested</Badge>;
  }
  return <Badge variant="info">Awaiting review</Badge>;
}

function SubmissionRow({
  submission,
  onGrade,
  onReturn,
}: {
  submission: PracticalSubmissionRead;
  onGrade: (id: string, grade: number | null, feedback: string | null) => void;
  onReturn: (id: string, feedback: string | null) => void;
}) {
  const [grade, setGrade] = useState(
    submission.grade === null ? "" : String(submission.grade),
  );
  const [feedback, setFeedback] = useState(submission.feedback ?? "");
  const [busy, setBusy] = useState(false);

  async function handleGrade() {
    setBusy(true);
    try {
      const parsed = grade.trim() === "" ? null : Number(grade);
      await onGrade(submission.id, parsed, feedback.trim() || null);
    } finally {
      setBusy(false);
    }
  }

  async function handleReturn() {
    setBusy(true);
    try {
      await onReturn(submission.id, feedback.trim() || null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-semibold text-ink">Learner hand-in</p>
        {statusBadge(submission.status)}
      </div>

      <pre className="mt-3 max-h-56 overflow-auto whitespace-pre-wrap rounded-lg bg-sand-100 px-3 py-2 font-mono text-[12px] leading-relaxed text-ink">
        {submission.content}
      </pre>

      <div className="mt-3 grid gap-3 sm:grid-cols-[120px_1fr]">
        <div>
          <label
            htmlFor={`grade-${submission.id}`}
            className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground"
          >
            Mark (0-100)
          </label>
          <Input
            id={`grade-${submission.id}`}
            className="mt-1"
            type="number"
            min={0}
            max={100}
            value={grade}
            onChange={(event) => setGrade(event.target.value)}
          />
        </div>
        <div>
          <label
            htmlFor={`feedback-${submission.id}`}
            className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground"
          >
            Feedback
          </label>
          <Textarea
            id={`feedback-${submission.id}`}
            className="mt-1 min-h-[70px]"
            value={feedback}
            onChange={(event) => setFeedback(event.target.value)}
            placeholder="What went well, and what to improve…"
          />
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <Button size="sm" disabled={busy} onClick={handleGrade}>
          {busy ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <CheckCircle2 className="h-4 w-4" />
          )}
          Save mark
        </Button>
        <Button size="sm" variant="outline" disabled={busy} onClick={handleReturn}>
          <RotateCcw className="h-4 w-4" />
          Return for revision
        </Button>
      </div>
    </div>
  );
}

/**
 * Lecturer review surface: learner progress, practical task hand-ins and
 * the recent activity feed for a published course.
 *
 * Marks and feedback written here are the learner's record on this
 * portal; Moodle remains the delivery surface for the lessons.
 */
export function LearnerReviewsPage() {
  const [courses, setCourses] = useState<MoodleCourseRead[]>([]);
  const [courseId, setCourseId] = useState<string>("");
  const [submissions, setSubmissions] = useState<PracticalSubmissionRead[]>([]);
  const [learners, setLearners] = useState<LecturerLearnerProgress[]>([]);
  const [activities, setActivities] = useState<LecturerActivityRead[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadCourse = useCallback(async (id: string) => {
    const [submissionRows, learnerRows, activityRows] = await Promise.all([
      api.lecturerSubmissions(id),
      api.lecturerLearners(id),
      api.lecturerActivities(id),
    ]);
    setSubmissions(submissionRows);
    setLearners(learnerRows);
    setActivities(activityRows);
  }, []);

  useEffect(() => {
    let active = true;

    api
      .listCourses()
      .then((response) => {
        if (!active) return;
        setCourses(response.courses);
        if (response.courses.length > 0) {
          setCourseId(response.courses[0].id);
        }
      })
      .catch((cause: unknown) => {
        if (!active) return;
        setError(
          cause instanceof Error
            ? cause.message
            : "Could not load the published courses.",
        );
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!courseId) return;
    let active = true;

    loadCourse(courseId)
      .catch((cause: unknown) => {
        if (!active) return;
        setError(
          cause instanceof Error
            ? cause.message
            : "Could not load the learner records.",
        );
      });

    return () => {
      active = false;
    };
  }, [courseId, loadCourse]);

  async function handleGrade(
    id: string,
    grade: number | null,
    feedback: string | null,
  ) {
    setError(null);
    setNotice(null);
    try {
      await api.lecturerGrade(id, { grade, feedback });
      await loadCourse(courseId);
      setNotice("The mark has been saved for the learner.");
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Could not save the mark.",
      );
    }
  }

  async function handleReturn(id: string, feedback: string | null) {
    setError(null);
    setNotice(null);
    try {
      await api.lecturerReturn(id, { feedback });
      await loadCourse(courseId);
      setNotice("The submission has been returned for revision.");
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Could not return the submission.",
      );
    }
  }

  const selectedCourse = courses.find((course) => course.id === courseId);

  return (
    <div className="space-y-7">
      <header>
        <h1 className="font-display text-2xl font-bold text-navy-900">
          Learner review
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Practical task hand-ins and learner progress for a published course.
        </p>
      </header>

      {error && (
        <div className="rounded-lg border border-brand/30 bg-brand/5 px-4 py-3 text-sm text-brand-800">
          {error}
        </div>
      )}

      {notice && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          {notice}
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="font-display text-base text-navy-900">
            Course
          </CardTitle>
          <CardDescription>
            Pick the course whose learners you want to review.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {courses.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No courses have been published yet.
            </p>
          ) : (
            <select
              className="h-10 w-full max-w-md rounded-md border border-input bg-card px-3 text-sm"
              value={courseId}
              onChange={(event) => setCourseId(event.target.value)}
              aria-label="Course to review"
            >
              {courses.map((course) => (
                <option key={course.id} value={course.id}>
                  {course.title}
                </option>
              ))}
            </select>
          )}
        </CardContent>
      </Card>

      {selectedCourse && (
        <>
          <section aria-labelledby="review-learners-heading" className="space-y-3">
            <h2
              id="review-learners-heading"
              className="flex items-center gap-2 font-display text-lg font-bold text-navy-900"
            >
              <Users className="h-4 w-4 text-brand-700" />
              Enrolled learners
            </h2>
            {learners.length === 0 ? (
              <Card>
                <CardContent className="py-8 text-center text-sm text-muted-foreground">
                  Nobody has enrolled in this course yet.
                </CardContent>
              </Card>
            ) : (
              <Card>
                <CardContent className="space-y-3 pt-6">
                  {learners.map((learner) => (
                    <div key={learner.enrolment_id} className="space-y-1.5">
                      <div className="flex flex-wrap items-baseline justify-between gap-2">
                        <p className="text-sm font-semibold text-ink">
                          {learner.full_name || learner.email}
                        </p>
                        <p className="text-[12px] text-muted-foreground">
                          {learner.completed_lessons}/{learner.total_lessons}{" "}
                          lessons &middot; {learner.submission_count} hand-in
                          {learner.submission_count === 1 ? "" : "s"}
                        </p>
                      </div>
                      <Progress value={learner.percentage} />
                      <p className="text-[11px] text-muted-foreground">
                        {learner.email}
                      </p>
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}
          </section>

          <section aria-labelledby="review-submissions-heading" className="space-y-3">
            <h2
              id="review-submissions-heading"
              className="flex items-center gap-2 font-display text-lg font-bold text-navy-900"
            >
              <MessageSquare className="h-4 w-4 text-brand-700" />
              Practical task hand-ins
            </h2>
            {submissions.length === 0 ? (
              <Card>
                <CardContent className="py-8 text-center text-sm text-muted-foreground">
                  No practical task has been handed in for this course yet.
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-3">
                {submissions.map((submission) => (
                  <SubmissionRow
                    key={submission.id}
                    submission={submission}
                    onGrade={handleGrade}
                    onReturn={handleReturn}
                  />
                ))}
              </div>
            )}
          </section>

          <section aria-labelledby="review-activity-heading" className="space-y-3">
            <h2
              id="review-activity-heading"
              className="flex items-center gap-2 font-display text-lg font-bold text-navy-900"
            >
              <Activity className="h-4 w-4 text-brand-700" />
              Recent activity
            </h2>
            <Card>
              <CardContent className="pt-6">
                {activities.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    No activity recorded for this course yet.
                  </p>
                ) : (
                  <ol className="space-y-2">
                    {activities.map((activity) => (
                      <li
                        key={activity.id}
                        className="flex flex-wrap items-baseline justify-between gap-2 border-b border-border/60 pb-2 last:border-0"
                      >
                        <span className="text-sm text-ink">{activity.summary}</span>
                        <span className="text-[11px] text-muted-foreground">
                          {new Date(activity.created_at).toLocaleString(undefined, {
                            day: "numeric",
                            month: "short",
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </span>
                      </li>
                    ))}
                  </ol>
                )}
              </CardContent>
            </Card>
          </section>
        </>
      )}
    </div>
  );
}
