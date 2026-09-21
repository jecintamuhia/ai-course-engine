import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { useParams, Link } from "react-router-dom";
import {
  Play,
  RotateCcw,
  AlertCircle,
  CalendarRange,
  BrainCircuit,
  Clock,
  Target,
  CornerDownRight,
  ArrowRight,
  Loader,
} from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/shared/PageHeader";
import { SectionHeader } from "@/components/shared/SectionHeader";
import { LoadingState } from "@/components/shared/LoadingState";
import { ErrorState } from "@/components/shared/ErrorState";
import { EmptyState } from "@/components/shared/EmptyState";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { IngestionStepper } from "@/components/shared/IngestionStepper";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { TopicCard } from "@/components/analysis/TopicCard";
import { DependencyGraph } from "@/components/analysis/DependencyGraph";

import { api, ApiError } from "@/lib/api";
import { formatBytes, formatDate, formatWorkload, formatMinutes } from "@/lib/format";
import { ingestBadge, curriculumBadge } from "@/lib/badges";
import { usePolling } from "@/hooks/usePolling";
import { getDraft } from "@/lib/drafts";
import { isActiveJob, TERMINAL_STATES } from "@/lib/status";
import { cn } from "@/lib/utils";

import type {
  DocumentOverview,
  CurriculumRead,
  TopicRead,
  DependencyGraphResponse,
} from "@/lib/types";

const difficultyLabels: Record<number, string> = {
  1: "Foundational",
  2: "Introductory",
  3: "Intermediate",
  4: "Advanced",
  5: "Expert",
};

const difficultyColors: Record<number, string> = {
  1: "bg-emerald-50 text-emerald-700 border-emerald-200",
  2: "bg-blue-50 text-blue-700 border-blue-200",
  3: "bg-amber-50 text-amber-700 border-amber-200",
  4: "bg-orange-50 text-orange-700 border-orange-200",
  5: "bg-red-50 text-red-700 border-red-200",
};

function flattenTopics(topics: TopicRead[], depth = 0): Array<{ topic: TopicRead; depth: number }> {
  const result: Array<{ topic: TopicRead; depth: number }> = [];
  for (const topic of topics) {
    result.push({ topic, depth });
    if (topic.subtopics?.length) result.push(...flattenTopics(topic.subtopics, depth + 1));
  }
  return result;
}

export function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [doc, setDoc] = useState<DocumentOverview | null>(null);
  const [curricula, setCurricula] = useState<CurriculumRead[]>([]);
  const [topics, setTopics] = useState<TopicRead[]>([]);
  const [pipelineRunning, setPipelineRunning] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [selectedTopicId, setSelectedTopicId] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const [docRes, curriculaRes, topicsRes] = await Promise.all([
        api.getDocumentOverview(id),
        api.listCurricula(id).catch(() => ({ curricula: [] })),
        api.listTopics(id).catch(() => []),
      ]);
      setDoc(docRes);
      setCurricula(curriculaRes.curricula ?? []);
      setTopics(Array.isArray(topicsRes) ? topicsRes : []);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  // Poll while job is active
  const jobId = doc?.latest_job?.id;
  const jobStatus = doc?.latest_job?.status;
  const isPolling = Boolean(id && jobId && isActiveJob(jobStatus));

  usePolling({
    fetcher: async () => {
      if (!jobId) return null;
      const job = await api.getIngestionJob(jobId);
      if (TERMINAL_STATES.includes(job.status) && id) {
        void load(); // refresh entire doc when job finishes
      }
      return job;
    },
    intervalMs: 2500,
    isDone: (job) => (job ? TERMINAL_STATES.includes(job.status) : true),
    enabled: isPolling,
  });

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!doc) return <EmptyState title="Document not found" />;

  const d = doc.document;
  const job = doc.latest_job;
  const readyForPipeline = !job || TERMINAL_STATES.includes(job.status);

  const handleStartJob = async () => {
    if (!id) return;
    setPipelineRunning(true);
    try {
      await api.createIngestionJob(id);
      toast.success("Processing started in the background.");
      void load();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : (err as Error).message;
      toast.error(msg);
    } finally {
      setPipelineRunning(false);
    }
  };

  const handleDependenciesAndGenerate = async () => {
    if (!id) return;
    setGenerating(true);
    try {
      await api.buildDependencies(id);
      toast.success("Dependencies resolved.");

      const draft = getDraft(id);
      await api.generateCurriculum({
        document_id: id,
        total_weeks: draft.total_weeks,
        learning_days_per_week: draft.learning_days_per_week,
        hours_per_day: 4,
        title: draft.title || undefined,
        description: draft.description || undefined,
      });
      toast.success("Curriculum generated successfully.");
      void load();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : (err as Error).message;
      toast.error(`Pipeline step failed: ${msg}`);
    } finally {
      setGenerating(false);
    }
  };

  const flatTopics = useMemo(() => flattenTopics(topics), [topics]);
  const topicMap = useMemo(() => {
    const map = new Map<string, TopicRead>();
    for (const { topic } of flatTopics) map.set(topic.id, topic);
    return map;
  }, [flatTopics]);

  // Read-only display graph: order + edges are derived client-side from real topics.
  const derivedGraph = useMemo<DependencyGraphResponse>(
    () => ({
      document_id: id ?? "",
      topological_order: topics.map((t) => t.id),
      rejected_cycle_edges: [],
      unresolved_prerequisites: [],
    }),
    [topics, id],
  );

  const resolvedEdgeCount = topics.reduce(
    (acc, topic) =>
      acc +
      topic.prerequisite_titles.filter((title) =>
        [...topicMap.values()].some((t) => t.title === title),
      ).length,
    0,
  );

  const selectedTopic = selectedTopicId ? (topicMap.get(selectedTopicId) ?? null) : null;

  const approvedCurriculum = curricula.find((c) => c.status === "approved");
  const publishedCurriculum = curricula.find((c) => c.status === "published");
  const firstCurriculum = curricula[0];

  return (
    <>
      <PageHeader
        eyebrow="Analysis workspace"
        title={d.original_filename}
        meta={`${formatBytes(d.size_bytes)} · Uploaded ${formatDate(d.created_at)} · SHA ${d.sha256_hash.slice(0, 16)}…`}
        actions={
          <div className="flex gap-2">
            {doc.topic_count > 0 && curricula.length === 0 && (
              <Button
                onClick={handleDependenciesAndGenerate}
                disabled={generating}
              >
                {generating ? (
                  <>
                    <Loader className="h-4 w-4 animate-spin" /> Generating…
                  </>
                ) : (
                  "Resolve dependencies → Generate curriculum"
                )}
              </Button>
            )}
            {readyForPipeline && (
              <Button
                onClick={handleStartJob}
                disabled={pipelineRunning}
                variant="outline"
              >
                {job?.status === "completed" ? (
                  <>
                    <RotateCcw className="h-4 w-4" /> Re-run full pipeline
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4" /> Start processing
                  </>
                )}
              </Button>
            )}
          </div>
        }
      />

      {/* Status grid */}
      <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Stat label="Latest job" value={job ? null : "Not processed"}>
          {job && <StatusBadge {...ingestBadge(job.status)} />}
        </Stat>
        <Stat label="Pages" value={doc.page_count} />
        <Stat label="Chapters" value={doc.chapter_count} />
        <Stat label="Chunks" value={doc.chunk_count} />
        <Stat label="Topics" value={doc.topic_count} />
        <Stat label="Curricula" value={doc.curriculum_count} />
      </div>

      {/* Pipeline */}
      {job && (
        <Card className="mb-5">
          <CardHeader className="pb-3">
            <SectionHeader
              icon={<BrainCircuit className="h-4 w-4" />}
              title="Pipeline progress"
              hint={job ? `started ${formatTimeSafe(job.started_at)}` : undefined}
              action={<StatusBadge {...ingestBadge(job.status)} />}
            />
          </CardHeader>
          <CardContent className="px-6 pb-6 pt-1">
            {isActiveJob(job.status) && (
              <div className="mb-4 flex items-center gap-2 rounded-lg border border-burgundy/20 bg-burgundy-50 px-4 py-2.5 text-xs text-burgundy-800">
                <Loader className="h-3.5 w-3.5 animate-spin" />
                Processing in background — this screen refreshes automatically.
              </div>
            )}
            <IngestionStepper
              jobStatus={job.status}
              trailing={[
                {
                  key: "curriculum",
                  label: "Curriculum",
                  detail: "Generate the course plan",
                  state: firstCurriculum ? "done" : "pending",
                  to: firstCurriculum ? `/curriculum/${firstCurriculum.id}` : undefined,
                },
                {
                  key: "review",
                  label: "Review",
                  detail: "Lecturer review before publish",
                  state: approvedCurriculum ? "done" : "pending",
                  to: approvedCurriculum ? `/curriculum/${approvedCurriculum.id}` : undefined,
                },
                {
                  key: "publish",
                  label: "Publish to Moodle",
                  detail: "Push approved course",
                  state: publishedCurriculum ? "done" : "pending",
                  to: publishedCurriculum ? `/publish/${publishedCurriculum.id}` : undefined,
                },
              ]}
            />
          </CardContent>
        </Card>
      )}

      {/* Traceability strip when pipeline is done */}
      {job && (job.status === "approved" || job.status === "completed") && (
        <div className="mb-5 rounded-xl border border-border bg-card px-4 py-3 text-[11px] text-muted-foreground shadow-card">
          Pipeline completed — text was derived from <strong className="font-semibold text-ink">source-derived</strong>{" "}
          extraction with <strong className="font-semibold text-ink">AI-assisted</strong> topic detection. Review the
          curriculum below before publishing.
        </div>
      )}

      {/* Job error */}
      {job?.status === "failed" && job.error_message && (
        <Card className="mb-5 border-red-200 bg-red-50">
          <CardContent className="p-4">
            <div className="flex items-start gap-2 text-sm text-red-800">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <div>
                <strong>Processing failed:</strong> {job.error_message}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Knowledge map / AI analysis */}
      <Card className="mb-5">
        <CardHeader className="pb-3">
          <SectionHeader
            icon={<BrainCircuit className="h-4 w-4" />}
            title="Knowledge map &amp; topics"
            hint={doc.topic_count > 0 ? `${flatTopics.length} nodes` : undefined}
          />
        </CardHeader>
        <CardContent>
          {doc.topic_count === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border bg-cream-50 px-6 py-12 text-center">
              <span className="flex h-11 w-11 items-center justify-center rounded-full bg-burgundy-50 text-burgundy ring-8 ring-burgundy/[0.05]">
                <BrainCircuit className="h-5 w-5" />
              </span>
              <p className="mt-3 text-sm font-semibold text-foreground">
                No topics analyzed yet
              </p>
              <p className="mt-1 max-w-sm text-xs leading-relaxed text-muted-foreground">
                {job?.status === "failed"
                  ? "The last pipeline run failed before topic analysis. Fix the underlying issue and re-run the pipeline to build the knowledge map."
                  : job
                    ? "Topic analysis has not produced results yet. Run the full pipeline to extract topics, concepts and dependencies."
                    : "Start the processing pipeline to extract topics, concepts, difficulty and the dependency map."}
              </p>
              {readyForPipeline && (
                <Button
                  className="mt-4"
                  variant="outline"
                  size="sm"
                  onClick={handleStartJob}
                  disabled={pipelineRunning}
                >
                  <Play className="h-3.5 w-3.5" />
                  {job?.status === "failed" ? "Re-run pipeline" : "Start processing"}
                </Button>
              )}
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
              <div className="min-w-0 lg:col-span-2">
                <div className="rounded-xl border border-border bg-cream-50/50 p-3">
                  <DependencyGraph
                    topics={topics}
                    graph={derivedGraph}
                    selectedTopicId={selectedTopicId}
                    onSelectTopic={setSelectedTopicId}
                  />
                </div>
                <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
                  Order shown is the AI-assessed learning sequence.{" "}
                  {resolvedEdgeCount > 0
                    ? `${resolvedEdgeCount} prerequisite relationships are drawn between topics.`
                    : "No prerequisite relationships were detected between topics."}{" "}
                  Node colors encode difficulty (green = foundational → red = expert). Select a
                  node to inspect it.
                </p>
              </div>

              <aside className="min-w-0">
                <div className="mb-2 flex items-center justify-between">
                  <h4 className="text-sm font-semibold text-foreground">
                    Topics ({flatTopics.length})
                  </h4>
                  <span className="text-[11px] text-muted-foreground">
                    incl. subtopics
                  </span>
                </div>
                <div className="max-h-[520px] space-y-2 overflow-y-auto pr-1">
                  {flatTopics.map(({ topic, depth }) => (
                    <div key={topic.id} className={cn(depth > 0 && "ml-6")}>
                      <TopicCard
                        topic={topic}
                        selected={selectedTopicId === topic.id}
                        onClick={() => setSelectedTopicId(topic.id)}
                      />
                    </div>
                  ))}
                </div>

                {selectedTopic && (
                  <div className="mt-3 rounded-xl border border-border bg-card p-4 shadow-card">
                    <div className="flex items-start justify-between gap-2">
                      <h4 className="text-sm font-semibold text-foreground">
                        {selectedTopic.title}
                      </h4>
                      <span
                        className={cn(
                          "inline-flex shrink-0 items-center rounded-md border px-2 py-0.5 text-[11px] font-medium",
                          difficultyColors[selectedTopic.difficulty],
                        )}
                      >
                        {difficultyLabels[selectedTopic.difficulty] ??
                          `Level ${selectedTopic.difficulty}`}
                      </span>
                    </div>
                    <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                      <span className="inline-flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {formatMinutes(selectedTopic.estimated_workload_minutes)}
                      </span>
                      <span className="text-border">·</span>
                      <span>{selectedTopic.concepts.length} concepts</span>
                    </div>

                    {selectedTopic.prerequisite_titles.length > 0 && (
                      <div className="mt-3">
                        <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                          Prerequisites
                        </div>
                        <div className="mt-1 flex flex-wrap gap-1.5">
                          {selectedTopic.prerequisite_titles.map((title) => {
                            const match = [...topicMap.values()].find((t) => t.title === title);
                            return match ? (
                              <button
                                key={title}
                                type="button"
                                onClick={() => setSelectedTopicId(match.id)}
                                className="inline-flex items-center gap-1 rounded-md border border-burgundy/20 bg-card px-2 py-0.5 text-[11px] font-medium text-burgundy-700 transition-colors hover:bg-burgundy-50"
                              >
                                <CornerDownRight className="h-3 w-3" />
                                {title}
                              </button>
                            ) : (
                              <span
                                key={title}
                                className="inline-flex items-center rounded-md bg-secondary/80 px-2 py-0.5 text-[11px] font-medium text-secondary-foreground"
                              >
                                {title}
                              </span>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {selectedTopic.learning_objectives.length > 0 && (
                      <div className="mt-3">
                        <div className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                          <Target className="h-3 w-3" />
                          Learning objectives
                        </div>
                        <ul className="mt-1 space-y-0.5">
                          {selectedTopic.learning_objectives.map((obj) => (
                            <li key={obj} className="text-xs leading-relaxed text-foreground/80">
                              {obj}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </aside>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Curriculum list */}
      <Card>
        <CardHeader className="pb-3">
          <SectionHeader
            icon={<CalendarRange className="h-4 w-4" />}
            title="Curricula for this document"
            hint={curricula.length > 0 ? `${curricula.length} version${curricula.length !== 1 ? "s" : ""}` : undefined}
          />
        </CardHeader>
        <CardContent>
          {curricula.length === 0 ? (
            <div className="rounded-xl border border-dashed border-border bg-cream-50 px-6 py-10 text-center text-sm text-muted-foreground">
              {doc.topic_count > 0 && !generating
                ? "No curriculum generated yet — click the pipeline button above to begin."
                : doc.topic_count === 0 && !job
                  ? "Start the processing pipeline above to analyze topics and generate a curriculum."
                  : "No curricula found."}
            </div>
          ) : (
            <div className="space-y-3">
              {curricula.map((c) => {
                const cb = curriculumBadge(c.status);
                return (
                  <Link
                    key={c.id}
                    to={`/curriculum/${c.id}`}
                    className="group flex items-center gap-4 rounded-xl border border-border bg-card px-4 py-3.5 shadow-card transition-all hover:border-burgundy/30 hover:shadow-lift"
                  >
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-burgundy-50 text-burgundy ring-4 ring-burgundy/[0.04]">
                      <CalendarRange className="h-[18px] w-[18px]" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="truncate text-sm font-semibold text-foreground">
                          {c.title}
                        </span>
                        <span className="rounded-md bg-cream-100 px-1.5 py-0.5 text-[10px] font-semibold text-muted-foreground">
                          v{c.version_number}
                        </span>
                      </div>
                      <div className="mt-0.5 text-xs text-muted-foreground">
                        {c.total_weeks} weeks · {formatWorkload(c.units)} total workload ·
                        generated {formatDate(c.created_at)}
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <StatusBadge {...cb} />
                      <ArrowRight className="h-4 w-4 text-muted-foreground/50 transition-transform group-hover:translate-x-0.5 group-hover:text-burgundy" />
                    </div>
                  </Link>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </>
  );
}

function Stat({
  label,
  value,
  children,
}: {
  label: string;
  value: string | number | null;
  children?: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-border bg-card px-3.5 py-3 shadow-card">
      <div className="flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        <span aria-hidden className="h-1 w-1 rounded-full bg-burgundy/60" />
        {label}
      </div>
      <div className="tnum mt-1 text-lg font-bold text-ink">
        {children ?? value ?? "—"}
      </div>
    </div>
  );
}

function formatTimeSafe(value: string | null | undefined): string {
  if (!value) return "recently";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "recently";
  return date.toLocaleString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  });
}