import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Award, CheckCircle2, Loader2, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { LearnerLoading } from "@/components/layout/LearnerShell";
import { ApiError, api } from "@/lib/api";
import type {
  LearnerAssessmentAnswer,
  LearnerAssessmentAttemptRead,
  LearnerFinalAssessmentRead,
} from "@/lib/types";

type DraftAnswer = { optionId: string | null; text: string };

function toAnswers(
  assessment: LearnerFinalAssessmentRead,
  draft: Record<number, DraftAnswer>,
): LearnerAssessmentAnswer[] {
  const answers: LearnerAssessmentAnswer[] = [];
  for (const question of assessment.questions) {
    const answer = draft[question.item_index];
    if (!answer) continue;
    if (answer.optionId) {
      answers.push({ item_index: question.item_index, option_id: answer.optionId });
    } else if (answer.text.trim()) {
      answers.push({ item_index: question.item_index, answer: answer.text });
    }
  }
  return answers;
}

export function LearnerAssessmentPage() {
  const { courseId = "" } = useParams();
  const [assessment, setAssessment] = useState<LearnerFinalAssessmentRead | null>(
    null,
  );
  const [draft, setDraft] = useState<Record<number, DraftAnswer>>({});
  const [result, setResult] = useState<LearnerAssessmentAttemptRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [certificateBusy, setCertificateBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  const load = useCallback(async () => {
    const response = await api.learnerFinalAssessment(courseId);
    setAssessment(response);
  }, [courseId]);

  useEffect(() => {
    let active = true;
    load()
      .catch((cause: unknown) => {
        if (!active) return;
        if (cause instanceof ApiError && cause.status === 409) {
          setUnavailable(true);
        } else {
          setError(
            cause instanceof Error
              ? cause.message
              : "Could not load the final assessment.",
          );
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [load]);

  const answeredCount = useMemo(
    () =>
      Object.values(draft).filter(
        (answer) => answer.optionId || answer.text.trim(),
      ).length,
    [draft],
  );

  async function handleRetry() {
    setError(null);
    setLoading(true);
    try {
      await load();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Could not load the final assessment.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit() {
    if (!assessment) return;
    setBusy(true);
    setError(null);
    try {
      const attempt = await api.learnerSubmitAssessment(
        courseId,
        toAnswers(assessment, draft),
      );
      setResult(attempt);
      setDraft({});
      await load();
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Could not submit your answers.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleCertificate() {
    setCertificateBusy(true);
    setError(null);
    try {
      await api.learnerRequestCertificate(courseId);
      await load();
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Could not issue your certificate.",
      );
    } finally {
      setCertificateBusy(false);
    }
  }

  if (loading) return <LearnerLoading />;

  if (unavailable) {
    return (
      <div className="space-y-4">
        <Button asChild variant="ghost" size="sm" className="-ml-2">
          <Link to={`/learn/course/${courseId}`}>
            <ArrowLeft className="h-4 w-4" />
            Back to the course
          </Link>
        </Button>
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            This course does not have an approved final assessment yet. Your
            lecturer will publish it when it is ready.
          </CardContent>
      </Card>
    </div>
  );
}

  if (!assessment) {
    return (
      <div className="space-y-4">
        <p className="text-sm text-brand-800">
          {error || "The final assessment could not be opened."}
        </p>
        <Button variant="outline" size="sm" onClick={handleRetry}>
          Try again
        </Button>
      </div>
    );
  }

  const certificate = assessment.certificate;
  const canRequestCertificate =
    assessment.all_lessons_completed && assessment.passed && !certificate;

  return (
    <div className="space-y-6">
      <Button asChild variant="ghost" size="sm" className="-ml-2">
        <Link to={`/learn/course/${courseId}`}>
          <ArrowLeft className="h-4 w-4" />
          Back to the course
        </Link>
      </Button>

      <section className="overflow-hidden rounded-2xl bg-navy-950 px-6 py-7 text-sand-100 sm:px-8">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-sand-100/60">
          Final assessment
        </p>
        <h1 className="mt-1 font-display text-2xl font-bold text-white sm:text-3xl">
          {assessment.title}
        </h1>
        {assessment.description && (
          <p className="mt-2 max-w-2xl text-sm text-sand-100/70">
            {assessment.description}
          </p>
        )}
        <dl className="mt-5 grid gap-3 text-sm sm:grid-cols-3">
          <div className="rounded-lg bg-navy-900/70 px-4 py-3">
            <dt className="text-[11px] uppercase tracking-[0.12em] text-sand-100/50">
              Pass mark
            </dt>
            <dd className="mt-0.5 font-semibold text-white">
              {assessment.pass_percent}%
            </dd>
          </div>
          <div className="rounded-lg bg-navy-900/70 px-4 py-3">
            <dt className="text-[11px] uppercase tracking-[0.12em] text-sand-100/50">
              Lessons complete
            </dt>
            <dd className="mt-0.5 font-semibold text-white">
              {assessment.completed_lessons} / {assessment.total_lessons}
            </dd>
          </div>
          <div className="rounded-lg bg-navy-900/70 px-4 py-3">
            <dt className="text-[11px] uppercase tracking-[0.12em] text-sand-100/50">
              Your best score
            </dt>
            <dd className="mt-0.5 font-semibold text-white">
              {assessment.best_score_percent === null
                ? "No attempts yet"
                : `${assessment.best_score_percent}%`}
            </dd>
          </div>
        </dl>
      </section>

      {error && (
        <div className="rounded-lg border border-brand/30 bg-brand/5 px-4 py-3 text-sm text-brand-800">
          {error}
        </div>
      )}

      {certificate && (
        <Card className="border-emerald-200 bg-emerald-50/60">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 font-display text-base text-emerald-900">
              <Award className="h-5 w-5" />
              Certificate issued
            </CardTitle>
            <CardDescription>
              Reference {certificate.reference} &middot;{" "}
              {new Date(certificate.issued_at).toLocaleDateString(undefined, {
                day: "numeric",
                month: "long",
                year: "numeric",
              })}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild variant="outline" size="sm">
              <Link to={`/verify/${certificate.reference}`}>
                View verification page
              </Link>
            </Button>
          </CardContent>
        </Card>
      )}

      {canRequestCertificate && (
        <Card className="border-emerald-200 bg-emerald-50/60">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 font-display text-base text-emerald-900">
              <Award className="h-5 w-5" />
              You have qualified for a certificate
            </CardTitle>
            <CardDescription>
              Every lesson is complete and you passed the final assessment with{" "}
              {assessment.best_score_percent}%.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              size="sm"
              disabled={certificateBusy}
              onClick={handleCertificate}
            >
              {certificateBusy ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Award className="h-4 w-4" />
              )}
              Issue my certificate
            </Button>
          </CardContent>
        </Card>
      )}

      {result && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 font-display text-base text-navy-900">
              {result.passed ? (
                <CheckCircle2 className="h-5 w-5 text-emerald-600" />
              ) : (
                <XCircle className="h-5 w-5 text-brand" />
              )}
              Attempt {result.attempt_number}: {result.score_percent}%
            </CardTitle>
            <CardDescription>
              {result.correct_count} of {result.auto_gradable_count} scored
              questions correct.{" "}
              {result.passed
                ? "You passed."
                : `You need ${assessment.pass_percent}% to pass.`}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {result.results.map((item) => (
              <div
                key={item.item_index}
                className="rounded-lg border border-border bg-sand-50/60 px-4 py-3"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <p className="text-sm font-semibold text-ink">
                    {item.item_index + 1}. {item.prompt}
                  </p>
                  {item.auto_graded ? (
                    <Badge variant={item.correct ? "success" : "warning"}>
                      {item.correct ? "Correct" : "Incorrect"}
                    </Badge>
                  ) : (
                    <Badge variant="info">Marked by lecturer</Badge>
                  )}
                </div>
                {item.correct_option_id && (
                  <p className="mt-2 text-[13px] text-muted-foreground">
                    Correct option:{" "}
                    <span className="font-medium text-ink">
                      {item.correct_answer || item.correct_option_id}
                    </span>
                  </p>
                )}
                {!item.correct_option_id && item.correct_answer && (
                  <p className="mt-2 text-[13px] text-muted-foreground">
                    Expected answer:{" "}
                    <span className="font-medium text-ink">
                      {item.correct_answer}
                    </span>
                  </p>
                )}
                {item.explanation && (
                  <p className="mt-1 text-[13px] text-muted-foreground">
                    {item.explanation}
                  </p>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="font-display text-base text-navy-900">
            Attempt history
          </CardTitle>
          <CardDescription>
            You can retake the assessment when you are ready; your best score is
            kept.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {assessment.attempts.length === 0 ? (
            <p className="text-sm text-muted-foreground">No attempts yet.</p>
          ) : (
            <ul className="space-y-2">
              {assessment.attempts.map((attempt) => (
                <li
                  key={attempt.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border px-4 py-2 text-sm"
                >
                  <span className="text-muted-foreground">
                    Attempt {attempt.attempt_number} &middot;{" "}
                    {new Date(attempt.submitted_at).toLocaleString(undefined, {
                      day: "numeric",
                      month: "short",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                  <span className="flex items-center gap-2">
                    <strong className="text-ink">{attempt.score_percent}%</strong>
                    <Badge variant={attempt.passed ? "success" : "warning"}>
                      {attempt.passed ? "Passed" : "Not passed"}
                    </Badge>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="font-display text-base text-navy-900">
            Questions
          </CardTitle>
          <CardDescription>
            {answeredCount} of {assessment.questions.length} questions answered.
            {assessment.auto_gradable_count < assessment.total_items
              ? ` ${assessment.total_items - assessment.auto_gradable_count} open-ended question(s) are reviewed by a lecturer and do not change your score.`
              : ""}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {assessment.questions.map((question) => {
            const answer = draft[question.item_index] ?? {
              optionId: null,
              text: "",
            };
            return (
              <fieldset
                key={question.item_index}
                className="rounded-lg border border-border px-4 py-3"
              >
                <legend className="px-1 text-sm font-semibold text-ink">
                  {question.item_index + 1}. {question.prompt}
                </legend>
                <p className="mt-1 text-[12px] text-muted-foreground">
                  {question.auto_gradable
                    ? "Scored automatically"
                    : "Open-ended — reviewed by a lecturer"}
                </p>
                {question.options.length > 0 ? (
                  <div className="mt-3 space-y-2">
                    {question.options.map((option) => (
                      <label
                        key={option.id}
                        className="flex cursor-pointer items-start gap-2 text-sm text-ink"
                      >
                        <input
                          type="radio"
                          name={`question-${question.item_index}`}
                          checked={answer.optionId === option.id}
                          onChange={() =>
                            setDraft((current) => ({
                              ...current,
                              [question.item_index]: {
                                optionId: option.id,
                                text: "",
                              },
                            }))
                          }
                          className="mt-0.5"
                        />
                        <span>{option.text}</span>
                      </label>
                    ))}
                  </div>
                ) : (
                  <textarea
                    className="mt-3 min-h-[100px] w-full rounded-lg border border-input bg-card p-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-brand"
                    placeholder="Type your answer"
                    value={answer.text}
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        [question.item_index]: {
                          optionId: null,
                          text: event.target.value,
                        },
                      }))
                    }
                    aria-label={`Answer for question ${question.item_index + 1}`}
                  />
                )}
              </fieldset>
            );
          })}

          <div className="flex flex-wrap items-center gap-2">
            <Button disabled={busy} onClick={handleSubmit}>
              {busy ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                "Submit attempt"
              )}
            </Button>
            <span className="text-[12px] text-muted-foreground">
              Your result is shown immediately.
            </span>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export function CertificateVerifyPage() {
  const { reference = "" } = useParams();
  const [record, setRecord] = useState<{
    learner_name: string;
    course_title: string;
    score_percent: number;
    issued_at: string;
    reference: string;
  } | null>(null);
  const [status, setStatus] = useState<"loading" | "verified" | "missing">(
    "loading",
  );

  useEffect(() => {
    let active = true;
    api
      .verifyCertificate(reference)
      .then((response) => {
        if (active) {
          setRecord(response);
          setStatus("verified");
        }
      })
      .catch(() => {
        if (active) setStatus("missing");
      });
    return () => {
      active = false;
    };
  }, [reference]);

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-2xl flex-col justify-center px-4 py-12">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 font-display text-xl text-navy-900">
            <Award className="h-6 w-6 text-brand" />
            Certificate verification
          </CardTitle>
          <CardDescription>Reference {reference}</CardDescription>
        </CardHeader>
        <CardContent>
          {status === "loading" && (
            <p className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Checking the register…
            </p>
          )}
          {status === "missing" && (
            <p className="flex items-center gap-2 text-sm text-brand-800">
              <XCircle className="h-4 w-4" />
              No certificate matches that reference.
            </p>
          )}
          {status === "verified" && record && (
            <div className="space-y-3 text-sm">
              <p className="flex items-center gap-2 font-semibold text-emerald-700">
                <CheckCircle2 className="h-4 w-4" />
                Certificate verified
              </p>
              <dl className="grid gap-2">
                <div>
                  <dt className="text-[11px] uppercase tracking-[0.12em] text-muted-foreground">
                    Awarded to
                  </dt>
                  <dd className="font-semibold text-ink">
                    {record.learner_name}
                  </dd>
                </div>
                <div>
                  <dt className="text-[11px] uppercase tracking-[0.12em] text-muted-foreground">
                    Course
                  </dt>
                  <dd className="font-semibold text-ink">
                    {record.course_title}
                  </dd>
                </div>
                <div>
                  <dt className="text-[11px] uppercase tracking-[0.12em] text-muted-foreground">
                    Score
                  </dt>
                  <dd className="font-semibold text-ink">
                    {record.score_percent}%
                  </dd>
                </div>
                <div>
                  <dt className="text-[11px] uppercase tracking-[0.12em] text-muted-foreground">
                    Issued
                  </dt>
                  <dd className="font-semibold text-ink">
                    {new Date(record.issued_at).toLocaleDateString(undefined, {
                      day: "numeric",
                      month: "long",
                      year: "numeric",
                    })}
                  </dd>
                </div>
              </dl>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
