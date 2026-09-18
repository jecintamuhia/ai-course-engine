import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  BookOpen,
  BrainCircuit,
  CalendarRange,
  FileText,
  GraduationCap,
  Lightbulb,
  Sparkles,
} from "lucide-react";

import { PageHeader } from "@/components/shared/PageHeader";
import { LoadingState } from "@/components/shared/LoadingState";
import { ErrorState } from "@/components/shared/ErrorState";
import { EmptyState } from "@/components/shared/EmptyState";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { ProgressPipeline } from "@/components/dashboard/ProgressPipeline";

import { api } from "@/lib/api";
import { formatWorkload, formatDate, formatBytes } from "@/lib/format";
import { curriculumBadge, ingestBadge } from "@/lib/badges";
import { cn } from "@/lib/utils";
import type {
  DashboardResponse,
  DocumentOverview,
  TopicRead,
  CurriculumRead,
} from "@/lib/types";

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

      // The "active" project: the most recent document with analysis activity,
      // falling back to the most recent upload.
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

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!stats) return null;

  // ----- If the library is empty, show a focused onboarding state -----
  if (documents.length === 0 || !activeDoc) {
    return (
      <>
        <PageHeader
          eyebrow="Course Intelligence Workspace"
          title="Your course engine"
          description="Ingest a textbook, let AI extract the course intelligence, design a 16-week curriculum, and publish it to Moodle."
        />
        <ProgressPipeline stats={stats} className="mb-6" />
        <EmptyState
          title="Start with your first textbook"
          description="Upload a PDF or DOCX and the pipeline will detect structure, extract topics, and draft a 16-week curriculum for lecturer review."
          actionLabel="Upload a textbook"
          actionTo="/upload"
        />
      </>
    );
  }

  const jobBadge = ingestBadge(activeDoc.latest_job?.status ?? null);
  const totalWorkload =
    activeCurricula.length > 0 ? formatWorkload(activeCurricula[0].units) : null;
  const conceptCount = activeTopics.reduce((a, t) => a + t.concepts.length, 0);
  const studyMinutes = activeTopics.reduce((a, t) => a + (t.estimated_workload_minutes || 0), 0);

  return (
    <>
      <PageHeader
        eyebrow="Course Intelligence Workspace"
        title="Dashboard"
        description="Textbook → AI understanding → 16-week curriculum → Moodle. Everything below is live data from the API."
        actions={
          <Link
            to="/upload"
            className="inline-flex h-9 items-center gap-2 rounded-md bg-burgundy px-4 text-sm font-medium text-cream-50 shadow-sm transition-colors hover:bg-burgundy-800"
          >
            <Sparkles className="h-4 w-4" />
            Upload textbook
          </Link>
        }
      />

      <ProgressPipeline stats={stats} className="mb-5" />

      {/* ----- Active textbook / hero ----- */}
      <section className="mb-5 overflow-hidden rounded-2xl border border-burgundy/20 bg-card">
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_auto]">
          <div className="flex flex-col gap-4 border-b border-border p-6 lg:border-b-0 lg:border-r">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-burgundy-700">
                <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-burgundy" />
                Active textbook
              </span>
              <StatusBadge tone={jobBadge.tone} label={jobBadge.label} />
            </div>
            <div className="min-w-0">
              <Link
                to={`/document/${activeDoc.document.id}`}
                className="text-lg font-bold tracking-tight text-foreground hover:text-burgundy-700"
              >
                {activeDoc.document.original_filename}
              </Link>
              <p className="mt-1 text-xs text-muted-foreground">
                {formatBytes(activeDoc.document.size_bytes)} · uploaded{" "}
                {formatDate(activeDoc.document.created_at)}
              </p>
            </div>
            <dl className="grid grid-cols-2 gap-x-8 gap-y-2 sm:grid-cols-4">
              <HeroStat value={activeDoc.page_count} label="Pages" />
              <HeroStat value={activeDoc.chapter_count} label="Chapters" />
              <HeroStat value={activeDoc.chunk_count} label="Chunks" />
              <HeroStat value={activeDoc.topic_count} label="Topics" />
            </dl>
          </div>
          <div className="flex flex-col justify-center gap-2 p-6 lg:items-end">
            <Link
              to={`/document/${activeDoc.document.id}`}
              className="inline-flex h-9 items-center justify-center gap-2 rounded-md bg-burgundy px-4 text-sm font-medium text-cream-50 shadow-sm transition-colors hover:bg-burgundy-800"
            >
              Open analysis workspace <ArrowRight className="h-4 w-4" />
            </Link>
            {activeDoc.topic_count > 0 && activeCurricula.length === 0 && (
              <Link
                to={`/document/${activeDoc.document.id}`}
                className="inline-flex h-9 items-center justify-center gap-2 rounded-md border border-border bg-card px-4 text-sm font-medium text-foreground transition-colors hover:border-burgundy/30 hover:text-burgundy-700"
              >
                <CalendarRange className="h-4 w-4" />
                Generate curriculum
              </Link>
            )}
          </div>
        </div>
      </section>

      {/* ----- Workspace body ----- */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <div className="min-w-0 space-y-5 lg:col-span-2">
          {/* Knowledge map */}
          <Section
            title="Knowledge map"
            hint={
              activeTopics.length > 0
                ? `${activeTopics.length} topics analyzed`
                : "Awaiting AI analysis"
            }
            actionTo={activeTopics.length > 0 ? `/document/${activeDoc.document.id}` : undefined}
            actionLabel={activeTopics.length > 0 ? "Open in workspace" : undefined}
            icon={BrainCircuit}
          >
            {activeTopics.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {activeTopics.slice(0, 24).map((topic) => (
                  <Link
                    key={topic.id}
                    to={`/document/${activeDoc.document.id}`}
                    className="inline-flex max-w-full items-center rounded-full border border-burgundy/20 bg-burgundy-50 px-3 py-1 text-xs font-medium text-burgundy-800 transition-colors hover:border-burgundy/40 hover:bg-burgundy-100"
                    title={topic.learning_objectives[0] ?? topic.title}
                  >
                    {topic.title}
                  </Link>
                ))}
                {activeTopics.length > 24 && (
                  <span className="inline-flex items-center rounded-full bg-secondary px-3 py-1 text-xs font-medium text-secondary-foreground">
                    +{activeTopics.length - 24} more
                  </span>
                )}
              </div>
            ) : (
              <SectionEmpty
                icon={BrainCircuit}
                title="No topics extracted yet"
                description="Run the AI pipeline on this textbook to extract topics, concepts, difficulty and the dependency map."
                actionLabel="Open textbook"
                actionTo={`/document/${activeDoc.document.id}`}
              />
            )}
          </Section>

          {/* Recent textbooks */}
          <Section
            title="Recent textbooks"
            hint={`${documents.length} in library`}
            actionTo="/documents"
            actionLabel="View all"
            icon={BookOpen}
          >
            <ul className="divide-y divide-border">
              {documents.slice(0, 6).map((doc) => {
                const badge = ingestBadge(doc.latest_job?.status ?? null);
                return (
                  <li key={doc.document.id}>
                    <Link
                      to={`/document/${doc.document.id}`}
                      className="group flex items-center gap-4 px-1 py-3 transition-colors first:pt-0 hover:bg-burgundy-50/30 sm:px-2"
                    >
                      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-burgundy-50 text-burgundy">
                        <FileText className="h-4 w-4" />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium text-foreground group-hover:text-burgundy-700">
                          {doc.document.original_filename}
                        </span>
                        <span className="block text-[11px] text-muted-foreground">
                          {doc.page_count} pages · {doc.chunk_count} chunks · {doc.topic_count}{" "}
                          topics
                        </span>
                      </span>
                      <StatusBadge tone={badge.tone} label={badge.label} />
                      <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
                    </Link>
                  </li>
                );
              })}
            </ul>
          </Section>
        </div>

        {/* ----- Right rail ----- */}
        <div className="min-w-0 space-y-5">
          {/* Curriculum preview */}
          <Section
            title="Curriculum preview"
            hint={activeCurricula.length > 0 ? "16-week plan" : "Not scheduled yet"}
            icon={CalendarRange}
          >
            {activeCurricula.length > 0 ? (
              <div className="space-y-4">
                {activeCurricula.map((c) => {
                  const cb = curriculumBadge(c.status);
                  return (
                    <Link
                      key={c.id}
                      to={`/curriculum/${c.id}`}
                      className="block rounded-lg border border-border p-3.5 transition-colors hover:border-burgundy/30"
                    >
                      <div className="mb-2.5 flex items-center justify-between gap-2">
                        <span className="truncate text-sm font-semibold text-foreground">
                          {c.title}
                        </span>
                        <StatusBadge tone={cb.tone} label={cb.label} />
                      </div>
                      <WeekStrip unit={c} />
                      <div className="mt-2 text-[11px] text-muted-foreground">
                        {c.total_weeks} weeks · {formatWorkload(c.units)} total
                      </div>
                    </Link>
                  );
                })}
              </div>
            ) : (
              <SectionEmpty
                icon={CalendarRange}
                title="No curriculum yet"
                description="Once topics are analyzed, generate a 16-week plan and review it before publishing."
                actionLabel={activeDoc.topic_count > 0 ? "Generate plan" : "Run analysis"}
                actionTo={`/document/${activeDoc.document.id}`}
              />
            )}
          </Section>

          {/* AI insights */}
          <Section
            title="AI insights"
            hint={activeTopics.length > 0 ? "From live analysis" : "Analysis pending"}
            icon={Lightbulb}
          >
            {activeTopics.length > 0 ? (
              <div className="space-y-3">
                <InsightRow
                  label="Topics analyzed"
                  value={String(activeTopics.length)}
                  detail="structured from the document"
                />
                <InsightRow
                  label="Concepts extracted"
                  value={String(conceptCount)}
                  detail="inside the topic knowledge map"
                />
                <InsightRow
                  label="Estimated study time"
                  value={`${Math.round(studyMinutes / 60)} h`}
                  detail={totalWorkload ? `planned curriculum: ${totalWorkload}` : "based on topic estimates"}
                />
                <p className="border-t border-border pt-3 text-xs leading-relaxed text-muted-foreground">
                  Topics are ready to be scheduled into a draft curriculum and submitted for
                  lecturer review.
                </p>
              </div>
            ) : (
              <SectionEmpty
                icon={Lightbulb}
                title="Awaiting analysis"
                description="AI analysis has not produced topics yet. Start the pipeline to build the knowledge map."
                actionLabel="Open textbook"
                actionTo={`/document/${activeDoc.document.id}`}
              />
            )}
          </Section>

          {/* Moodle connection */}
          {stats.moodle && (
            <Section title="Moodle" hint="Publishing destination" icon={GraduationCap}>
              <div className="space-y-2 text-sm">
                <ConnectionRow label="Connection" value={stats.moodle.connected ? "Connected" : "Disconnected"} ok={stats.moodle.connected ?? false} />
                <ConnectionRow label="Site" value={stats.moodle.site_name ?? "—"} />
                {stats.moodle.error && (
                  <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">
                    {stats.moodle.error}
                  </div>
                )}
                <Link
                  to="/status"
                  className="inline-flex items-center gap-1 text-xs font-semibold text-burgundy-700 hover:text-burgundy-800"
                >
                  Detailed check <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </div>
            </Section>
          )}
        </div>
      </div>
    </>
  );
}

type IconType = typeof BrainCircuit;

function Section({
  title,
  hint,
  icon: Icon,
  actionTo,
  actionLabel,
  children,
}: {
  title: string;
  hint?: string;
  icon: IconType;
  actionTo?: string;
  actionLabel?: string;
  children: ReactNode;
}) {
  return (
    <section className="overflow-hidden rounded-xl border border-border bg-card">
      <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
        <div className="flex min-w-0 items-center gap-2.5">
          {Icon && <Icon className="h-4 w-4 shrink-0 text-burgundy" />}
          <h3 className="truncate text-sm font-semibold text-foreground">{title}</h3>
          {hint && <span className="hidden text-[11px] text-muted-foreground sm:inline">· {hint}</span>}
        </div>
        {actionTo && actionLabel && (
          <Link
            to={actionTo}
            className="inline-flex shrink-0 items-center gap-1 text-xs font-semibold text-burgundy-700 hover:text-burgundy-800"
          >
            {actionLabel} <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        )}
      </div>
      <div className="p-4">{children}</div>
    </section>
  );
}

function SectionEmpty({
  icon: Icon,
  title,
  description,
  actionLabel,
  actionTo,
}: {
  icon: IconType;
  title: string;
  description: string;
  actionLabel: string;
  actionTo: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border bg-muted/20 px-6 py-8 text-center">
      <span className="flex h-10 w-10 items-center justify-center rounded-full bg-burgundy-50 text-burgundy">
        <Icon className="h-5 w-5" />
      </span>
      <p className="mt-3 text-sm font-semibold text-foreground">{title}</p>
      <p className="mt-1 max-w-xs text-xs leading-relaxed text-muted-foreground">{description}</p>
      <Link
        to={actionTo}
        className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-burgundy-700 hover:text-burgundy-800"
      >
        {actionLabel} <ArrowRight className="h-3.5 w-3.5" />
      </Link>
    </div>
  );
}

function HeroStat({ value, label }: { value: number; label: string }) {
  return (
    <div>
      <dt className="sr-only">{label}</dt>
      <dd className="text-xl font-bold tracking-tight tabular-nums text-foreground">
        {value ?? 0}
      </dd>
      <div className="text-[11px] font-medium text-muted-foreground">{label}</div>
    </div>
  );
}

function WeekStrip({ unit }: { unit: CurriculumRead }) {
  const total = Math.min(unit.total_weeks, 16);
  const weeks = Array.from({ length: total }, (_, i) => i + 1);
  return (
    <div>
      <div className="flex gap-1">
        {weeks.map((week) => {
          const hasUnit = unit.units.some((u) => u.week_number === week);
          const unitTitle = unit.units.find((u) => u.week_number === week)?.title;
          return (
            <span
              key={week}
              title={hasUnit ? `Week ${week}: ${unitTitle}` : `Week ${week}`}
              className={cn(
                "h-1.5 flex-1 rounded-full",
                hasUnit ? "bg-burgundy" : "bg-border",
              )}
            />
          );
        })}
      </div>
      <div className="mt-1 flex justify-between text-[9px] font-medium text-muted-foreground">
        <span>Week 01</span>
        <span>Week {unit.total_weeks}</span>
      </div>
    </div>
  );
}

function InsightRow({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <div>
        <div className="text-xs font-medium text-muted-foreground">{label}</div>
        {detail && <div className="text-[10px] text-muted-foreground/70">{detail}</div>}
      </div>
      <div className="shrink-0 text-base font-bold tabular-nums text-foreground">{value}</div>
    </div>
  );
}

function ConnectionRow({ label, value, ok }: { label: string; value: string; ok?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="flex items-center gap-1.5 text-xs font-medium text-foreground">
        <span
          className={cn(
            "h-1.5 w-1.5 rounded-full",
            ok === undefined ? "bg-border" : ok ? "bg-emerald-500" : "bg-red-500",
          )}
        />
        {value}
      </span>
    </div>
  );
}