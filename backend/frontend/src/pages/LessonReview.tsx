import { useEffect, useMemo, useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  ArrowLeft,
  Check,
  ChevronDown,
  ChevronRight,
  FlaskConical,
  Loader2,
  ShieldCheck,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/shared/PageHeader";
import { LoadingState } from "@/components/shared/LoadingState";
import { ErrorState } from "@/components/shared/ErrorState";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

import { api } from "@/lib/api";
import { lessonBadge } from "@/lib/badges";
import type {
  BlockReviewStatus,
  CurriculumDetailRead,
  LessonBlockRead,
  LessonBlockType,
  LessonRead,
  LessonSourceMapRead,
} from "@/lib/types";

type ReviewOutcome = "approved" | "rejected";

const BLOCK_TYPE_LABELS: Record<LessonBlockType, string> = {
  text: "Text",
  heading: "Heading",
  example: "Example",
  diagram: "Diagram",
  table: "Table",
  external_resource: "External resource",
  video: "Video",
  activity: "Activity",
  knowledge_check: "Knowledge check",
  summary: "Summary",
};

function blockTone(status: BlockReviewStatus): "success" | "danger" | "neutral" {
  if (status === "approved") return "success";
  if (status === "rejected") return "danger";
  return "neutral";
}

function blockLabel(status: BlockReviewStatus): string {
  if (status === "approved") return "Approved";
  if (status === "rejected") return "Rejected";
  return "Generated";
}

function renderBlockPayload(block: LessonBlockRead): string {
  const p = block.payload ?? {};
  const bits: string[] = [];
  for (const key of [
    "content",
    "text",
    "instructions",
    "question",
    "description",
    "caption",
    "url",
    "reason",
  ]) {
    const value = p[key];
    if (typeof value === "string" && value.trim()) bits.push(value.trim());
  }
  if (block.block_type === "knowledge_check") {
    const options = Array.isArray(p.options) ? (p.options as unknown[]) : [];
    const optionBits = options
      .map((o) => {
        const text = (o as { text?: unknown })?.text;
        return typeof text === "string" && text.trim() ? text.trim() : null;
      })
      .filter((value): value is string => value !== null);
    if (optionBits.length > 0) {
      bits.push(`Options: ${optionBits.join(" | ")}`);
    }
    const correct = String(p.correct_option_id ?? "");
    const answer = options
      .map((o) => o as { id?: unknown; text?: unknown })
      .find((o) => String(o.id) === correct)?.text;
    bits.push(`Correct answer: ${typeof answer === "string" ? answer : correct}`);
  }
  if (block.block_type === "diagram" && Array.isArray(p.nodes)) {
    const nodes = (p.nodes as { label?: string }[])
      .map((n) => n.label ?? "")
      .filter(Boolean);
    if (nodes.length > 0) bits.push(`Diagram nodes: ${nodes.join(", ")}`);
  }
  return bits.length > 0 ? bits.slice(0, 4).join("\n") : JSON.stringify(p);
}

export function LessonReviewPage() {
  const { curriculumId, unitId } = useParams<{
    curriculumId: string;
    unitId: string;
  }>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [curriculum, setCurriculum] = useState<CurriculumDetailRead | null>(null);
  const [lessons, setLessons] = useState<LessonRead[]>([]);
  const [generating, setGenerating] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [busyLesson, setBusyLesson] = useState<string | null>(null);
  const [reviewerName, setReviewerName] = useState("");
  const [reviewComments, setReviewComments] = useState("");
  const [sourceMap, setSourceMap] = useState<LessonSourceMapRead | null>(null);

  const unit = useMemo(
    () =>
      curriculum?.units.find((u) => u.id === unitId) ?? null,
    [curriculum, unitId],
  );

  const load = async () => {
    if (!unitId) return;
    setLoading(true);
    setError(null);
    try {
      if (curriculumId) {
        setCurriculum(await api.getCurriculum(curriculumId));
      }
      const list = await api.listWeekLessons(unitId);
      setLessons(list.lessons);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [curriculumId, unitId]);

  const toggleExpand = async (lessonId: string) => {
    if (expanded === lessonId) {
      setExpanded(null);
      setSourceMap(null);
      return;
    }
    setExpanded(lessonId);
    setSourceMap(null);
    try {
      const source = await api.getLessonSourceMap(lessonId);
      setSourceMap(source);
    } catch {
      setSourceMap(null);
    }
  };

  const generate = async () => {
    if (!unitId) return;
    setGenerating(true);
    try {
      const result = await api.generateWeekContent(unitId);
      setLessons((prev) => {
        const kept = prev.filter(
          (l) =>
            !result.generated.some((g) => g.id === l.id) &&
            !result.generated.some((g) => g.topic_id === l.topic_id),
        );
        return [...kept, ...result.generated];
      });
      toast.success(
        result.generated.length > 0
          ? `Generated ${result.generated.length} lesson(s).`
          : "No new lessons were generated.",
      );
      if (result.skipped.length > 0) {
        toast.info(`${result.skipped.length} topic(s) skipped.`);
      }
      if (result.errors.length > 0) {
        toast.warning(`${result.errors.length} component(s) failed.`);
      }
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setGenerating(false);
      void load();
    }
  };

  const submitLesson = async (lessonId: string) => {
    setBusyLesson(lessonId);
    try {
      await api.submitLessonForReview(lessonId);
      toast.success("Submitted for review.");
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusyLesson(null);
      void load();
    }
  };

  const reviewLesson = async (lessonId: string, outcome: ReviewOutcome) => {
    setBusyLesson(lessonId);
    try {
      await api.reviewLesson(lessonId, {
        decision: outcome,
        reviewer_name: reviewerName || null,
        comments: reviewComments || null,
      });
      toast.success(
        outcome === "approved"
          ? `Lesson approved — it will be published to Moodle.`
          : "Lesson rejected.",
      );
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusyLesson(null);
      setReviewComments("");
      void load();
    }
  };

  const reviewBlock = async (
    blockId: string,
    lessonId: string,
    outcome: ReviewOutcome,
  ) => {
    setBusyLesson(lessonId);
    try {
      await api.reviewBlock(blockId, {
        review_status: outcome,
        comments: reviewComments || null,
      });
      toast.success(
        outcome === "approved" ? "Block approved." : "Block rejected.",
      );
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusyLesson(null);
      setReviewComments("");
      void load();
    }
  };

  const regenerateBlock = async (blockId: string, lessonId: string) => {
    setBusyLesson(lessonId);
    try {
      await api.regenerateBlock(blockId);
      toast.success("Block regenerated.");
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusyLesson(null);
      void load();
    }
  };

  const removeBlock = async (blockId: string, lessonId: string) => {
    setBusyLesson(lessonId);
    try {
      await api.deleteBlock(blockId);
      toast.success("Block deleted.");
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusyLesson(null);
      void load();
    }
  };

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <>
      <PageHeader
        eyebrow="Course content"
        title={
          unit
            ? `Week ${unit.week_number}: ${unit.title}`
            : "Lesson review"
        }
        description={
          curriculum
            ? `${curriculum.title} — generate, review, and approve lessons before they reach Moodle.`
            : "Generate, review, and approve lessons for this week."
        }
        actions={
          curriculum && (
            <Link
              to={`/curriculum/${curriculum.id}`}
              className="inline-flex items-center gap-1 text-xs font-semibold text-burgundy-700 hover:text-burgundy-800"
            >
              <ArrowLeft className="h-3.5 w-3.5" /> Curriculum
            </Link>
          )
        }
      />

      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <Badge variant="outline">
            {lessons.length} lesson{lessons.length === 1 ? "" : "s"}
          </Badge>
          {unit && <Badge variant="outline">Week {unit.week_number}</Badge>}
        </div>
        <Button onClick={generate} disabled={generating} variant="ai">
          {generating ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <FlaskConical className="h-4 w-4" />
          )}
          {generating ? "Generating…" : "Generate lessons"}
        </Button>
      </div>

      {lessons.length === 0 ? (
        <Card>
          <CardContent className="py-14 text-center">
            <Sparkles className="mx-auto mb-3 h-8 w-8 text-burgundy/40" />
            <p className="text-sm font-medium text-foreground">
              No lessons for this week yet.
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Generate lessons from the week's source topics, then review them below.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {lessons.map((lesson) => {
            const badge = lessonBadge(lesson.status);
            const isExpanded = expanded === lesson.id;
            return (
              <Card key={lesson.id}>
                <CardContent className="p-5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <StatusBadge tone={badge.tone} label={badge.label} />
                        <span className="text-xs text-muted-foreground">
                          {lesson.blocks.length} block
                          {lesson.blocks.length === 1 ? "" : "s"} ·{" "}
                          {lesson.estimated_workload_minutes} min
                        </span>
                      </div>
                      <h3
                        className="mt-1.5 text-base font-semibold text-ink"
                      >
                        {lesson.title}
                      </h3>
                      <p className="mt-0.5 text-sm text-muted-foreground">
                        {lesson.description}
                      </p>
                      {lesson.generation_errors.length > 0 && (
                        <div className="mt-2 space-y-1">
                          {lesson.generation_errors.map((err, i) => (
                            <p
                              key={i}
                              className="text-xs text-amber-700"
                            >
                              ⚠ {err.component ?? "component"}:{" "}
                              {err.reason ?? err.message ?? "not generated"}
                            </p>
                          ))}
                        </div>
                      )}
                    </div>
                    <div className="flex shrink-0 flex-wrap items-center gap-2">
                      {lesson.status !== "approved" && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => submitLesson(lesson.id)}
                          disabled={busyLesson === lesson.id || generating}
                        >
                          {busyLesson === lesson.id ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <ShieldCheck className="h-3.5 w-3.5" />
                          )}
                          Submit for review
                        </Button>
                      )}
                      {lesson.status === "awaiting_review" && (
                        <>
                          <Button
                            variant="success"
                            size="sm"
                            onClick={() => reviewLesson(lesson.id, "approved")}
                            disabled={busyLesson === lesson.id}
                          >
                            <Check className="h-3.5 w-3.5" /> Approve
                          </Button>
                          <Button
                            variant="destructive"
                            size="sm"
                            onClick={() => reviewLesson(lesson.id, "rejected")}
                            disabled={busyLesson === lesson.id}
                          >
                            <X className="h-3.5 w-3.5" /> Reject
                          </Button>
                        </>
                      )}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => toggleExpand(lesson.id)}
                      >
                        {isExpanded ? (
                          <ChevronDown className="h-4 w-4" />
                        ) : (
                          <ChevronRight className="h-4 w-4" />
                        )}
                        {isExpanded ? "Collapse" : "Review"}
                      </Button>
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="mt-5 space-y-5">
                      {lesson.status === "awaiting_review" && (
                        <div className="grid gap-3 rounded-lg border border-border bg-cream-100/50 p-4 sm:grid-cols-[1fr_1fr_auto]">
                          <div>
                            <Label htmlFor={`reviewer-${lesson.id}`}>
                              Reviewer name
                            </Label>
                            <Input
                              id={`reviewer-${lesson.id}`}
                              value={reviewerName}
                              onChange={(e) => setReviewerName(e.target.value)}
                              placeholder="Lecturer name"
                              className="mt-1"
                            />
                          </div>
                          <div>
                            <Label htmlFor={`comments-${lesson.id}`}>Comments</Label>
                            <Textarea
                              id={`comments-${lesson.id}`}
                              value={reviewComments}
                              onChange={(e) => setReviewComments(e.target.value)}
                              placeholder="Optional review notes"
                              className="mt-1"
                            />
                          </div>
                          <div className="flex items-end gap-2">
                            <Button
                              variant="success"
                              size="sm"
                              onClick={() => reviewLesson(lesson.id, "approved")}
                              disabled={busyLesson === lesson.id}
                            >
                              <Check className="h-3.5 w-3.5" /> Approve lesson
                            </Button>
                            <Button
                              variant="destructive"
                              size="sm"
                              onClick={() => reviewLesson(lesson.id, "rejected")}
                              disabled={busyLesson === lesson.id}
                            >
                              <X className="h-3.5 w-3.5" /> Reject lesson
                            </Button>
                          </div>
                        </div>
                      )}

                      <Separator />

                      {/* Blocks */}
                      <div className="space-y-3">
                        {lesson.blocks.map((block) => (
                          <div
                            key={block.id}
                            className="rounded-lg border border-border bg-card p-4"
                          >
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <div className="flex flex-wrap items-center gap-2">
                                <Badge variant="outline">
                                  {BLOCK_TYPE_LABELS[block.block_type]}
                                </Badge>
                                <Badge variant={blockTone(block.review_status)}>
                                  {blockLabel(block.review_status)}
                                </Badge>
                                {block.title && (
                                  <span className="text-sm font-medium text-ink">
                                    {block.title}
                                  </span>
                                )}
                              </div>
                              <div className="flex flex-wrap items-center gap-1.5">
                                <Button
                                  variant="success"
                                  size="sm"
                                  onClick={() =>
                                    reviewBlock(block.id, lesson.id, "approved")
                                  }
                                  disabled={busyLesson === lesson.id}
                                >
                                  <Check className="h-3.5 w-3.5" /> Approve
                                </Button>
                                <Button
                                  variant="destructive"
                                  size="sm"
                                  onClick={() =>
                                    reviewBlock(block.id, lesson.id, "rejected")
                                  }
                                  disabled={busyLesson === lesson.id}
                                >
                                  <X className="h-3.5 w-3.5" /> Reject
                                </Button>
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() =>
                                    regenerateBlock(block.id, lesson.id)
                                  }
                                  disabled={busyLesson === lesson.id}
                                >
                                  <FlaskConical className="h-3.5 w-3.5" /> Regenerate
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => removeBlock(block.id, lesson.id)}
                                  disabled={busyLesson === lesson.id}
                                >
                                  <Trash2 className="h-3.5 w-3.5" />
                                </Button>
                              </div>
                            </div>
                            <pre className="mt-2 whitespace-pre-wrap rounded-md bg-cream-100/70 p-3 text-xs leading-relaxed text-foreground/80">
                              {renderBlockPayload(block)}
                            </pre>
                            {block.review_comments && (
                              <p className="mt-2 text-xs text-muted-foreground">
                                <strong>Note:</strong> {block.review_comments}
                              </p>
                            )}
                          </div>
                        ))}
                      </div>

                      {/* Source map */}
                      {sourceMap && sourceMap.sources.length > 0 && (
                        <div>
                          <h4 className="mb-2 text-xs font-semibold uppercase tracking-[0.15em] text-muted-foreground">
                            Source grounding
                          </h4>
                          <div className="space-y-2">
                            {sourceMap.sources.map((src) => (
                              <div
                                key={src.chunk_id}
                                className="rounded-lg border border-border bg-cream-100/40 p-3"
                              >
                                <p className="text-xs leading-relaxed text-foreground/75">
                                  {src.content}
                                </p>
                                <p className="mt-1.5 text-[11px] text-muted-foreground">
                                  p. {src.page_number ?? "—"} · cited by{" "}
                                  {src.cited_by.length} block
                                  {src.cited_by.length === 1 ? "" : "s"}
                                </p>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </>
  );
}