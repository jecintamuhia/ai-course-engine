import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  ArrowDown,
  ArrowRight,
  BookOpen,
  BrainCircuit,
  CalendarRange,
  CheckCircle2,
  ClipboardCheck,
  Clock,
  FileText,
  GraduationCap,
  Layers,
  Lightbulb,
  Network,
  Sparkles,
  Upload,
} from "lucide-react";

import { SectionHeader } from "@/components/shared/SectionHeader";
import { MetricCard } from "@/components/shared/MetricCard";
import { Loader } from "@/components/shared/Loader";
import { LoadingState } from "@/components/shared/LoadingState";
import { ErrorState } from "@/components/shared/ErrorState";
import { EmptyState } from "@/components/shared/EmptyState";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { ProgressPipeline } from "@/components/dashboard/ProgressPipeline";
import { PipelineStrip, type PipelineStage } from "@/components/shared/PipelineStrip";
import { ActivityTimeline, type ActivityItem } from "@/components/shared/ActivityTimeline";
import { AIInsight } from "@/components/shared/AIInsight";

import { api } from "@/lib/api";
import { formatWorkload, formatDate, formatBytes } from "@/lib/format";
import { curriculumBadge, ingestBadge } from "@/lib/badges";
import { INGESTION_STEP_LABELS, INGESTION_STEP_ORDER } from "@/lib/status";
import type { Tone } from "@/lib/status";
import { cn } from "@/lib/utils";
import type {
  CurriculumRead,
  DashboardResponse,
  DocumentOverview,
  IngestionState,
  TopicRead,
} from "@/lib/types";

const DIFFICULTY_DOT: Record<number, string> = {
  1: "bg-emerald-500",
  2: "bg-sky-500",
  3: "bg-amber-500",
  4: "bg-orange-500",
  5: "bg-red-500",
};

function flattenTopics(topics: TopicRead[]): TopicRead[] {
  const result: TopicRead[] = [];
  const walk = (list: TopicRead[]) => {
    for (const topic of list) {
      result.push(topic);
      if (topic.subtopics?.length) walk(topic.subtopics);
    }
  };
  walk(topics);
  return result;
}

export function DashboardPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<DashboardResponse | null>(null);
  const [documents, setDocuments] = useState<DocumentOverview[]>([]);
  const [activeTopics, setActiveTopics] = useState<TopicRead[]>([]);
  const [activeCurricula, setActiveCurricula] = useState<CurriculumRead[]>([]);
  const [activeDoc, setActiveDoc] = useState<DocumentOverview | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [dashRes, docsRes] = await Promise.all([
        api.dashboard(),
        api.listDocuments(),
      ]);
      setStats(dashRes);
      const docs = docsRes.documents ?? [];
      setDocuments(docs);

      const doc =
        docs.find((d) => d.topic_count > 0 || d.curriculum_count > 0) ?? docs[0] ?? null;
      setActiveDoc(doc);

      if (doc) {
        const [topicsRes, curriculaRes] = await Promise.all([
          api.listTopics(doc.document.id).catch(() => []),
          api.listCurricula(doc.document.id).catch(() => ({ curricula: [] })),
        ]);
        setActiveTopics(Array.isArray(topicsRes) ? topicsRes : []);
        setActiveCurricula((curriculaRes.curricula ?? []).slice(0, 3));
      } else {
        setActiveTopics([]);
        setActiveCurricula([]);
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  if (loading) return <LoadingState message="Loading your workspace…" />;
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!stats) return null;

  const onboarding = documents.length === 0 || !activeDoc;
  const jobBadge = onboarding
    ? null
    : ingestBadge(activeDoc!.latest_job?.status ?? null);
  const flatTopics = flattenTopics(activeTopics);
  const conceptCount = flatTopics.reduce((a, t) => a + t.concepts.length, 0);
  const studyMinutes = flatTopics.reduce(
    (a, t) => a + (t.estimated_workload_minutes || 0),
    0,
  );
  const totalWorkload =
    activeCurricula.length > 0 ? formatWorkload(activeCurricula[0].units) : null;

  const heroStages: PipelineStage[] = buildHeroStages(stats, activeTopics.length > 0, activeCurricula);

  return (
    <>
      <Hero heroStages={heroStages} />

      {/* Metric cards */}
      <section
        aria-label="Workspace metrics"
        className="mb-6 grid grid-cols-2 gap-4 xl:grid-cols-4"
      >
        <MetricCard
          label="Textbooks"
          value={stats.documents_total}
          icon={<BookOpen className="h-4 w-4" />}
          tone="primary"
          context={
            <>
              <Layers className="h-3.5 w-3.5 text-muted-foreground" />
              {stats.documents_processing > 0 ? (
                <>
                  {stats.documents_processing} in AI processing
                  <Loader className="ml-0.5 h-3 w-3 text-brand" />
                </>
              ) : (
                "all processing settled"
              )}
            </>
          }
          to="/documents"
        />
        <MetricCard
          label="Curricula"
          value={stats.curricula_total}
          icon={<CalendarRange className="h-4 w-4" />}
          tone="primary"
          context={
            <>
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
              {stats.curricula_approved} approved
            </>
          }
          to="/documents"
        />
        <MetricCard
          label="Pending reviews"
          value={stats.curricula_pending_review}
          icon={<ClipboardCheck className="h-4 w-4" />}
          tone={stats.curricula_pending_review > 0 ? "warning" : "neutral"}
          context={
            stats.curricula_pending_review > 0
              ? "lecturer decision needed"
              : "nothing awaiting review"
          }
        />
        <MetricCard
          label="Published courses"
          value={stats.courses_published}
          icon={<GraduationCap className="h-4 w-4" />}
          tone={stats.courses_published > 0 ? "success" : "neutral"}
          context={
            stats.moodle?.site_name ? `on ${stats.moodle.site_name}` : "not published yet"
          }
          to="/courses"
        />
      </section>

      {/* Product pipeline (real counts) */}
      <ProgressPipeline stats={stats} className="mb-6" />

      {onboarding ? (
        <EmptyState
          title="Start with your first textbook"
          description="Upload a PDF or DOCX and the pipeline will detect structure, extract topics, and draft a 16-week curriculum for lecturer review."
          actionLabel="Upload a textbook"
          actionTo="/upload"
        />
      ) : (
        <WorkspaceBody
          stats={stats}
          documents={documents}
          activeDoc={activeDoc!}
          activeTopics={activeTopics}
          activeCurricula={activeCurricula}
          jobBadgeTone={jobBadge!.tone}
          jobBadgeLabel={jobBadge!.label}
          flatTopics={flatTopics}
          conceptCount={conceptCount}
          studyMinutes={studyMinutes}
          totalWorkload={totalWorkload}
        />
      )}
    </>
  );
}

/* ------------------------------------------------------------------ */
/* Hero                                                                 */
/* ------------------------------------------------------------------ */

function Hero({ heroStages }: { heroStages: PipelineStage[] }) {
  return (
    <section className="relative mb-6 overflow-hidden rounded-2xl border border-brand-800/60 bg-brand-900 text-sand-100 shadow-lift">
      {/* washes */}
      <span
        aria-hidden
        className="pointer-events-none absolute -right-24 -top-28 h-80 w-80 rounded-full bg-brand-600/30 blur-3xl"
      />
      <span
        aria-hidden
        className="pointer-events-none absolute -bottom-32 left-1/4 h-72 w-72 rounded-full bg-brand-700/25 blur-3xl"
      />

      <div className="relative grid gap-8 p-6 sm:p-8 lg:grid-cols-[1.2fr_1fr] lg:items-center lg:p-10">
        <div className="max-w-2xl">
          <p className="inline-flex items-center gap-2 rounded-full border border-sand-100/15 bg-sand-100/[0.06] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-sand-100/80">
            <Sparkles className="h-3.5 w-3.5 text-sand-100/90" />
            AI Course Intelligence Workspace
          </p>
          <h1 className="mt-4 text-3xl font-bold leading-[1.1] tracking-tight text-sand-50 sm:text-4xl lg:text-[42px]">
            Turn textbooks into intelligent learning pathways.
          </h1>
          <p className="mt-4 max-w-xl text-[15px] leading-relaxed text-sand-100/75">
            Upload a textbook and let AI extract its structure, map concepts and
            dependencies, build a 16-week curriculum, and prepare it for Moodle —
            reviewed by a lecturer before anything is published.
          </p>
          <div className="mt-6 flex flex-wrap items-center gap-3">
            <Link
              to="/upload"
              className="inline-flex h-11 items-center gap-2 rounded-md bg-sand-50 px-6 text-sm font-semibold text-brand-900 shadow-sm transition-colors hover:bg-sand-100"
            >
              <Upload className="h-4 w-4" />
              Upload textbook
            </Link>
            <Link
              to="/documents"
              className="inline-flex h-11 items-center gap-2 rounded-md border border-sand-100/20 px-6 text-sm font-semibold text-sand-50 transition-colors hover:bg-sand-100/10"
            >
              <CalendarRange className="h-4 w-4" />
              View curricula
            </Link>
          </div>
        </div>

        <div className="rounded-xl border border-sand-100/10 bg-brand-950/40 p-5 backdrop-blur-sm">
          <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-sand-100/50">
            <BrainCircuit className="h-3.5 w-3.5" />
            The pipeline
          </div>
          <div className="mt-4 flex flex-col gap-1">
            {heroStages.map((stage, index) => (
              <NavStageRow key={stage.key} stage={stage} index={index} />
            ))}
          </div>
          <p className="mt-4 border-t border-sand-100/10 pt-3 text-[11px] text-sand-100/50">
            Every stage reflects live workspace activity.
          </p>
        </div>
      </div>
    </section>
  );
}

function NavStageRow({ stage, index }: { stage: PipelineStage; index: number }) {
  const state = stage.state ?? "pending";
  return (
    <span className="flex items-center gap-2.5 text-sm">
      <span className="w-5 text-right text-[10px] font-bold tabular-nums text-sand-100/40">
        {String(index + 1).padStart(2, "0")}
      </span>
      <span
        className={cn(
          "h-1.5 w-1.5 shrink-0 rounded-full",
          state === "done" && "bg-emerald-400",
          state === "active" && "bg-sand-50 animate-pulse-soft",
          state === "pending" && "bg-sand-100/20",
        )}
      />
      <span
        className={cn(
          "font-semibold",
          state === "done" ? "text-sand-50" : state === "active"
            ? "text-sand-50"
            : "text-sand-100/45",
        )}
      >
        {stage.label}
      </span>
      {state === "active" && (
        <Loader className="ml-auto h-3.5 w-3.5 text-sand-100/70" />
      )}
      <span className="ml-auto text-[11px] text-sand-100/50">
        {state === "done" ? "ready" : state === "active" ? "in progress" : "next"}
      </span>
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Main workspace body                                                  */
/* ------------------------------------------------------------------ */

interface WorkspaceBodyProps {
  stats: DashboardResponse;
  documents: DocumentOverview[];
  activeDoc: DocumentOverview;
  activeTopics: TopicRead[];
  activeCurricula: CurriculumRead[];
  jobBadgeTone: Tone;
  jobBadgeLabel: string;
  flatTopics: TopicRead[];
  conceptCount: number;
  studyMinutes: number;
  totalWorkload: string | null;
}

function WorkspaceBody({
  stats,
  documents,
  activeDoc,
  activeTopics,
  activeCurricula,
  jobBadgeTone,
  jobBadgeLabel,
  flatTopics,
  conceptCount,
  studyMinutes,
  totalWorkload,
}: WorkspaceBodyProps) {
  const activity = buildActivity(documents);
  const chain = buildPreviewChain(flatTopics);
  const availableObjectives = flatTopics.reduce((a, t) => a + t.learning_objectives.length, 0);

  return (
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
      <div className="min-w-0 space-y-6 xl:col-span-2">
        {/* Active textbook */}
        <ActiveProject
          activeDoc={activeDoc}
          activeTopics={activeTopics}
          activeCurricula={activeCurricula}
          docTopicsCount={activeDoc.topic_count}
          conceptCount={conceptCount}
          availableObjectives={availableObjectives}
          jobBadgeTone={jobBadgeTone}
          jobBadgeLabel={jobBadgeLabel}
        />

        {/* Knowledge map preview */}
        <section className="overflow-hidden rounded-2xl border border-border bg-card shadow-card">
          <div className="border-b border-border px-5 py-4">
            <SectionHeader
              icon={<Network className="h-4 w-4 text-brand" />}
              title="Knowledge map preview"
              hint={
                activeTopics.length > 0
                  ? `${flatTopics.length} topics analyzed`
                  : "Awaiting AI analysis"
              }
              action={
                flatTopics.length > 0 ? (
                  <Link
                    to={`/document/${activeDoc.document.id}`}
                    className="inline-flex items-center gap-1 text-xs font-semibold text-brand-700 hover:text-brand-800"
                  >
                    Explore knowledge map <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                ) : undefined
              }
            />
          </div>
          <div className="p-5">
            {chain.length > 0 ? (
              <div className="flex flex-col items-stretch gap-0">
                {chain.map((entry, i) => (
                  <div key={entry.id}>
                    <div className="flex items-center justify-between gap-3 rounded-lg border border-border bg-sand-100/60 px-3.5 py-2.5">
                      <div className="flex min-w-0 items-center gap-2.5">
                        <span
                          aria-hidden
                          className={cn(
                            "h-2 w-2 shrink-0 rounded-full",
                            DIFFICULTY_DOT[entry.difficulty] ?? "bg-muted-foreground",
                          )}
                        />
                        <span className="truncate text-[13px] font-medium text-ink">
                          {entry.title}
                        </span>
                      </div>
                      <span className="shrink-0 text-[10px] tabular-nums text-muted-foreground">
                        level {entry.difficulty}
                      </span>
                    </div>
                    {i < chain.length - 1 && (
                      <div className="flex items-center gap-3 py-1 pl-7">
                        <span
                          className={cn(
                            "h-5 w-px",
                            entry.prereq ? "bg-emerald-400" : "bg-border",
                          )}
                        />
                        <span className="flex items-center gap-1 text-[10px] font-medium text-muted-foreground">
                          <ArrowDown className="h-3 w-3" />
                          {entry.prereq ? "prerequisite of next topic" : "learning sequence"}
                        </span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-10 text-center">
                <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand">
                  <Network className="h-5 w-5" />
                </span>
                <p className="mt-3 text-sm font-semibold text-ink">No topics extracted yet</p>
                <p className="mt-1 max-w-sm text-xs leading-relaxed text-muted-foreground">
                  Run the AI pipeline on this textbook to build the concept and dependency map.
                </p>
                <Link
                  to={`/document/${activeDoc.document.id}`}
                  className="mt-4 inline-flex items-center gap-1 text-xs font-semibold text-brand-700 hover:text-brand-800"
                >
                  Open textbook workspace <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </div>
            )}
          </div>
        </section>

        {/* Recent textbooks */}
        <section className="overflow-hidden rounded-2xl border border-border bg-card shadow-card">
          <div className="border-b border-border px-5 py-4">
            <SectionHeader
              icon={<BookOpen className="h-4 w-4 text-brand" />}
              title="Recent textbooks"
              hint={`${documents.length} in library`}
              action={
                <Link
                  to="/documents"
                  className="inline-flex items-center gap-1 text-xs font-semibold text-brand-700 hover:text-brand-800"
                >
                  View all <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              }
            />
          </div>
          <ul className="divide-y divide-border">
            {documents.slice(0, 5).map((doc) => {
              const badge = ingestBadge(doc.latest_job?.status ?? null);
              return (
                <li key={doc.document.id}>
                  <Link
                    to={`/document/${doc.document.id}`}
                    className="group flex items-center gap-4 px-5 py-3.5 transition-colors hover:bg-sand-100/70"
                  >
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand">
                      <FileText className="h-4 w-4" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium text-ink group-hover:text-brand-700">
                        {doc.document.original_filename}
                      </span>
                      <span className="block text-[11px] text-muted-foreground">
                        {doc.page_count} pages · {doc.chunk_count} chunks · {doc.topic_count}{" "}
                        topics · {formatDate(doc.document.created_at)}
                      </span>
                    </span>
                    <StatusBadge tone={badge.tone} label={badge.label} />
                    <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
                  </Link>
                </li>
              );
            })}
          </ul>
        </section>
      </div>

      {/* Right rail */}
      <div className="min-w-0 space-y-6">
        <CurriculumPreview activeDoc={activeDoc} curricula={activeCurricula} />

        <section className="overflow-hidden rounded-2xl border border-border bg-card shadow-card">
          <div className="border-b border-border px-5 py-4">
            <SectionHeader
              icon={<Lightbulb className="h-4 w-4 text-ai" />}
              title="AI insights"
              description={
                activeTopics.length > 0
                  ? "What the model discovered from this textbook"
                  : "Analysis pending"
              }
            />
          </div>
          <div className="p-5">
            {flatTopics.length > 0 ? (
              <div className="space-y-3">
                <AIInsight title="Learning structure">
                  AI identified{" "}
                  <strong className="font-semibold text-ink">
                    {flatTopics.length} learning topic{flatTopics.length !== 1 && "s"}
                  </strong>{" "}
                  across the document
                  {conceptCount > 0 && (
                    <>
                      , grouped around{" "}
                      <strong className="font-semibold text-ink">{conceptCount}</strong>{" "}
                      concept{conceptCount !== 1 && "s"}
                    </>
                  )}
                  .
                </AIInsight>
                <InsightRow
                  label="Learning objectives"
                  value={String(availableObjectives)}
                  detail="written from the source material"
                />
                <InsightRow
                  label="Est. study time"
                  value={`${Math.round(studyMinutes / 60)} h`}
                  detail={totalWorkload ? `planned curriculum: ${totalWorkload}` : "from topic estimates"}
                />
                <div className="flex items-center justify-between rounded-lg border border-brand/15 bg-brand-50/50 px-3 py-2.5 text-xs">
                  <span className="text-brand-900">
                    {flatTopics.length > 0
                      ? "Topics are ready to be scheduled into a curriculum."
                      : "Run analysis to build the knowledge map."}
                  </span>
                  <Link
                    to={`/document/${activeDoc.document.id}`}
                    className="shrink-0 font-semibold text-brand-700 hover:text-brand-800"
                  >
                    Open
                  </Link>
                </div>
              </div>
            ) : (
              <div className="py-8 text-center">
                <p className="text-sm font-semibold text-ink">Awaiting analysis</p>
                <p className="mx-auto mt-1 max-w-xs text-xs leading-relaxed text-muted-foreground">
                  AI analysis has not produced topics yet for this textbook.
                </p>
              </div>
            )}
          </div>
        </section>

        <section className="overflow-hidden rounded-2xl border border-border bg-card shadow-card">
          <div className="border-b border-border px-5 py-4">
            <SectionHeader
              icon={<Clock className="h-4 w-4 text-brand" />}
              title="Recent activity"
              description="Uploads and AI pipeline events from live records"
            />
          </div>
          <div className="p-5">
            {activity.length > 0 ? (
              <ActivityTimeline items={activity.slice(0, 6)} />
            ) : (
              <p className="py-6 text-center text-xs text-muted-foreground">
                No activity recorded yet.
              </p>
            )}
          </div>
        </section>

        {stats.moodle && (
          <MoodleCard
            connected={stats.moodle.connected ?? false}
            siteName={stats.moodle.site_name}
            error={stats.moodle.error}
            published={stats.courses_published}
          />
        )}
      </div>
    </div>
  );
}

function ActiveProject({
  activeDoc,
  activeTopics,
  activeCurricula,
  docTopicsCount,
  conceptCount,
  availableObjectives,
  jobBadgeTone,
  jobBadgeLabel,
}: {
  activeDoc: DocumentOverview;
  activeTopics: TopicRead[];
  activeCurricula: CurriculumRead[];
  docTopicsCount: number;
  conceptCount: number;
  availableObjectives: number;
  jobBadgeTone: WorkspaceBodyProps["jobBadgeTone"];
  jobBadgeLabel: string;
}) {
  const job = activeDoc.latest_job;
  const stages: PipelineStage[] = buildProjectStages(
    job?.status ?? null,
    activeTopics.length > 0,
    activeCurricula,
  );

  return (
    <section className="overflow-hidden rounded-2xl border border-brand/20 bg-card shadow-card">
      <div className="relative p-5 sm:p-6">
        <span
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 h-28 bg-gradient-to-b from-brand/[0.05] to-transparent"
        />
        <div className="relative">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.16em] text-brand-700">
              <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-brand" />
              Active textbook
            </span>
            <StatusBadge tone={jobBadgeTone} label={jobBadgeLabel} />
            {activeCurricula.length > 0 && (
              <StatusBadge tone={curriculumBadge(activeCurricula[0].status).tone} label="Curriculum ready" />
            )}
          </div>

          <div className="mt-4 flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
            <div className="min-w-0">
              <Link
                to={`/document/${activeDoc.document.id}`}
                className="text-xl font-bold tracking-tight text-ink hover:text-brand-700"
              >
                {activeDoc.document.original_filename}
              </Link>
              <p className="mt-1 text-xs text-muted-foreground">
                {formatBytes(activeDoc.document.size_bytes)} · uploaded{" "}
                {formatDate(activeDoc.document.created_at)}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Link
                to={`/document/${activeDoc.document.id}`}
                className="inline-flex h-9 items-center gap-2 rounded-md bg-brand px-4 text-sm font-medium text-sand-50 shadow-sm transition-colors hover:bg-brand-800"
              >
                Open workspace <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </div>

          <dl className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <ProjectStat value={activeDoc.page_count} label="Pages" />
            <ProjectStat value={activeDoc.chapter_count} label="Chapters" />
            <ProjectStat value={docTopicsCount} label="Topics" />
            <ProjectStat value={conceptCount} label="Concepts" />
          </dl>

          <div className="mt-5 border-t border-border pt-4">
            <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
              Project pipeline
            </div>
            <PipelineStrip stages={stages} compact />
            {availableObjectives > 0 && (
              <p className="mt-3 text-[11px] text-muted-foreground">
                {availableObjectives} learning objective{availableObjectives !== 1 && "s"}{" "}
                extracted across topics{activeTopics.length > 0 ? ` · ${activeTopics.length} top-level` : ""}.
              </p>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

function ProjectStat({ value, label }: { value: number; label: string }) {
  return (
    <div className="rounded-lg border border-border bg-sand-100/50 px-3.5 py-2.5">
      <div className="tnum text-xl font-bold tracking-tight text-ink">{value ?? 0}</div>
      <div className="text-[11px] font-medium text-muted-foreground">{label}</div>
    </div>
  );
}

function CurriculumPreview({
  activeDoc,
  curricula,
}: {
  activeDoc: DocumentOverview;
  curricula: CurriculumRead[];
}) {
  const c = curricula[0] ?? null;
  return (
    <section className="overflow-hidden rounded-2xl border border-border bg-card shadow-card">
      <div className="border-b border-border px-5 py-4">
        <SectionHeader
          icon={<CalendarRange className="h-4 w-4 text-brand" />}
          title="Curriculum"
          hint={c ? `v${c.version_number} · ${c.total_weeks} weeks` : "Not planned yet"}
          action={
            c ? (
              <Link
                to={c.status === "approved" || c.status === "published" ? `/publish/${c.id}` : `/curriculum/${c.id}`}
                className="inline-flex items-center gap-1 text-xs font-semibold text-brand-700 hover:text-brand-800"
              >
                {c.status === "approved" || c.status === "published"
                  ? "Publish"
                  : "Open studio"}{" "}
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            ) : undefined
          }
        />
      </div>
      <div className="p-5">
        {c ? (
          <div className="space-y-3">
            <div className="flex items-center justify-between gap-2">
              <span className="truncate text-sm font-semibold text-ink">{c.title}</span>
              <StatusBadge {...curriculumBadge(c.status)} />
            </div>
            <WeekStrip unit={c} />
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-border pt-3 text-[11px] text-muted-foreground">
              <span>{c.units.length} weekly units</span>
              <span>·</span>
              <span>{formatWorkload(c.units)} total</span>
              <span>·</span>
              <span>{c.learning_days_per_week} days/week</span>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand">
              <CalendarRange className="h-5 w-5" />
            </span>
            <p className="mt-3 text-sm font-semibold text-ink">No curriculum yet</p>
            <p className="mt-1 max-w-xs text-xs leading-relaxed text-muted-foreground">
              {activeDoc.topic_count > 0
                ? "Generate the 16-week plan from the analyzed topics."
                : "AI analysis must finish before a curriculum can be generated."}
            </p>
          </div>
        )}
      </div>
    </section>
  );
}

function MoodleCard({
  connected,
  siteName,
  error,
  published,
}: {
  connected: boolean;
  siteName: string | null;
  error: string | null;
  published: number;
}) {
  return (
    <section className="overflow-hidden rounded-2xl border border-border bg-card shadow-card">
      <div className="border-b border-border px-5 py-4">
        <SectionHeader
          icon={<GraduationCap className="h-4 w-4 text-brand" />}
          title="Moodle"
          description="Publishing destination"
          action={
            <Link
              to="/status"
              className="inline-flex items-center gap-1 text-xs font-semibold text-brand-700 hover:text-brand-800"
            >
              Details <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          }
        />
      </div>
      <div className="space-y-2.5 p-5 text-sm">
        <div className="flex items-center justify-between gap-3">
          <span className="text-xs text-muted-foreground">Connection</span>
          <span className="flex items-center gap-1.5 text-xs font-medium text-ink">
            <span
              aria-hidden
              className={cn("h-1.5 w-1.5 rounded-full", connected ? "bg-emerald-500" : "bg-red-500")}
            />
            {connected ? "Connected" : "Disconnected"}
          </span>
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="text-xs text-muted-foreground">Site</span>
          <span className="truncate text-xs font-medium text-ink">{siteName ?? "—"}</span>
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="text-xs text-muted-foreground">Published</span>
          <span className="tnum text-xs font-medium text-ink">
            {published} course{published !== 1 && "s"}
          </span>
        </div>
        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs leading-relaxed text-red-800">
            {error}
          </div>
        )}
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Small pieces                                                        */
/* ------------------------------------------------------------------ */

function WeekStrip({ unit }: { unit: CurriculumRead }) {
  const total = Math.min(unit.total_weeks, 16);
  const weeks = Array.from({ length: total }, (_, i) => i + 1);
  return (
    <div>
      <div className="flex h-6 items-end gap-[3px]">
        {weeks.map((week) => {
          const hasUnit = unit.units.some((u) => u.week_number === week);
          const unitTitle = unit.units.find((u) => u.week_number === week)?.title;
          return (
            <span
              key={week}
              title={hasUnit ? `Week ${week}: ${unitTitle}` : `Week ${week}`}
              className={cn(
                "flex-1 rounded-sm transition-colors",
                hasUnit
                  ? "bg-gradient-to-t from-brand to-brand-500"
                  : "bg-border",
              )}
            />
          );
        })}
      </div>
      <div className="mt-1.5 flex justify-between text-[10px] font-medium text-muted-foreground">
        <span>Week 01</span>
        <span>Week {unit.total_weeks}</span>
      </div>
    </div>
  );
}

function InsightRow({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-t border-border pt-3">
      <div className="min-w-0">
        <div className="text-xs font-medium text-muted-foreground">{label}</div>
        {detail && <div className="truncate text-[10px] text-muted-foreground/70">{detail}</div>}
      </div>
      <div className="shrink-0 text-base font-bold tabular-nums text-ink">{value}</div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Derived data helpers (all from real API payloads)                    */
/* ------------------------------------------------------------------ */

const HERO_STAGES = [
  "Textbook",
  "AI analysis",
  "Knowledge map",
  "Curriculum",
  "Review",
  "Moodle",
] as const;

function buildHeroStages(
  stats: DashboardResponse,
  hasTopics: boolean,
  curricula: CurriculumRead[],
): PipelineStage[] {
  const reviewPending = curricula.some((c) => c.status === "awaiting_review");
  const approved = curricula.some((c) =>
    ["approved", "published"].includes(c.status),
  );
  const published = curricula.some((c) => c.status === "published");
  const stateFor = (index: number): PipelineStage["state"] => {
    switch (index) {
      case 0:
        return stats.documents_total > 0 ? "done" : "pending";
      case 1:
        return stats.documents_processing > 0
          ? "active"
          : stats.documents_total > 0
            ? "done"
            : "pending";
      case 2:
        return hasTopics ? "done" : stats.documents_total > 0 ? "active" : "pending";
      case 3:
        return curricula.length > 0 ? "done" : hasTopics ? "active" : "pending";
      case 4:
        return approved || published ? "done" : reviewPending ? "active" : "pending";
      case 5:
        return published ? "done" : approved ? "active" : "pending";
      default:
        return "pending";
    }
  };
  return HERO_STAGES.map((label, index) => ({
    key: String(index),
    label,
    state: stateFor(index),
  }));
}

const PROJECT_POST_STAGES = ["Curriculum", "Review", "Moodle"] as const;

function buildProjectStages(
  jobStatus: IngestionJobStatus,
  hasTopics: boolean,
  curricula: CurriculumRead[],
): PipelineStage[] {
  const base: PipelineStage[] = INGESTION_STEP_ORDER.map((key, index) => {
    let state: PipelineStage["state"] = "pending";
    if (jobStatus === "completed") {
      state = "done";
    } else if (jobStatus === "failed" || jobStatus === "cancelled") {
      state = "pending";
    } else if (jobStatus) {
      const idx = INGESTION_STEP_ORDER.indexOf(
        jobStatus as (typeof INGESTION_STEP_ORDER)[number],
      );
      if (idx >= 0) {
        state = index < idx ? "done" : index === idx ? "active" : "pending";
      }
    }
    return {
      key,
      label: shortLabel(INGESTION_STEP_LABELS[key].title),
      state,
    };
  });

  const reviewPending = curricula.some((c) => c.status === "awaiting_review");
  const approved = curricula.some((c) =>
    ["approved", "published"].includes(c.status),
  );
  const published = curricula.some((c) => c.status === "published");

  const postStates: PipelineStage["state"][] = [
    curricula.length > 0 ? "done" : hasTopics ? "active" : "pending",
    approved || published ? "done" : reviewPending ? "active" : "pending",
    published ? "done" : approved ? "active" : "pending",
  ];

  return [
    ...base,
    ...PROJECT_POST_STAGES.map((label, i) => ({
      key: `post-${label}`,
      label,
      state: postStates[i],
    })),
  ];
}

function shortLabel(label: string): string {
  return label.replace("detect ", "").replace(" AI", "");
}

type IngestionJobStatus = IngestionState | null | undefined;

function buildPreviewChain(topics: TopicRead[]): Array<{
  id: string;
  title: string;
  difficulty: number;
  prereq: boolean;
}> {
  const pick = topics.slice(0, 6);
  return pick.map((t, i) => ({
    id: t.id,
    title: t.title,
    difficulty: t.difficulty,
    prereq: i > 0 ? t.prerequisite_titles.includes(pick[i - 1].title) : false,
  }));
}

function buildActivity(documents: DocumentOverview[]): ActivityItem[] {
  const items: ActivityItem[] = [];
  for (const doc of documents) {
    const job = doc.latest_job;
    if (job) {
      const jobItem = jobActivity(job.status, job.completed_at ?? job.started_at ?? job.created_at);
      if (jobItem) {
        items.push({
          id: `job-${job.id}`,
          title: jobItem.title,
          description: doc.document.original_filename,
          timestamp: jobItem.timestamp,
          icon: jobItem.icon,
          tone: jobItem.tone,
        });
      }
    }
    items.push({
      id: `doc-${doc.document.id}`,
      title: "Textbook uploaded",
      description: doc.document.original_filename,
      timestamp: doc.document.created_at,
      icon: <UploadIcon />,
      tone: "neutral",
    });
  }
  return items.sort(
    (a, b) =>
      (b.timestamp ? Date.parse(b.timestamp) : 0) -
      (a.timestamp ? Date.parse(a.timestamp) : 0),
  );
}

function UploadIcon() {
  return <Upload className="h-3.5 w-3.5" />;
}

function jobActivity(
  status: string | null,
  ts: string,
): { title: string; timestamp: string; icon: ReactNode; tone: ActivityItem["tone"] } | null {
  switch (status) {
    case "completed":
      return {
        title: "AI analysis completed",
        timestamp: ts,
        icon: <CheckCircle2 className="h-3.5 w-3.5" />,
        tone: "success",
      };
    case "failed":
      return {
        title: "Pipeline failed",
        timestamp: ts,
        icon: <span className="text-[9px]">✕</span>,
        tone: "danger",
      };
    case "awaiting_review":
      return {
        title: "Ready for review",
        timestamp: ts,
        icon: <ClipboardCheck className="h-3.5 w-3.5" />,
        tone: "warning",
      };
    case "approved":
      return {
        title: "Analysis approved",
        timestamp: ts,
        icon: <CheckCircle2 className="h-3.5 w-3.5" />,
        tone: "success",
      };
    default:
      return null;
  }
}