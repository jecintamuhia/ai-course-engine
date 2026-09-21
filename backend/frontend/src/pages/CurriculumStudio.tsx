import { useEffect, useMemo, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

import { PageHeader } from "@/components/shared/PageHeader";
import { LoadingState } from "@/components/shared/LoadingState";
import { ErrorState } from "@/components/shared/ErrorState";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { WeekSidebar } from "@/components/curriculum/WeekSidebar";
import { WeekCard } from "@/components/curriculum/WeekCard";
import { AIInsightPanel } from "@/components/curriculum/AIInsightPanel";
import { ReviewPanel } from "@/components/curriculum/ReviewPanel";
import { Card, CardContent } from "@/components/ui/card";

import { api } from "@/lib/api";
import { formatMinutes, formatWorkload } from "@/lib/format";
import { curriculumBadge } from "@/lib/badges";
import type { CurriculumDetailRead } from "@/lib/types";

export function CurriculumStudioPage() {
  const { id } = useParams<{ id: string }>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [curriculum, setCurriculum] = useState<CurriculumDetailRead | null>(null);
  const [selectedWeek, setSelectedWeek] = useState<number>(1);

  const load = async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const c = await api.getCurriculum(id);
      setCurriculum(c);
      // Keep selection valid
      if (c.units.length > 0) {
        setSelectedWeek((prev) =>
          c.units.some((u) => u.week_number === prev)
            ? prev
            : c.units[0].week_number,
        );
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [id]);

  const selectedUnit = useMemo(
    () => curriculum?.units.find((u) => u.week_number === selectedWeek) ?? null,
    [curriculum, selectedWeek],
  );

  const totalMinutes = curriculum
    ? curriculum.units.reduce((a, u) => a + u.estimated_workload_minutes, 0)
    : 0;

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!curriculum) return null;

  const badge = curriculumBadge(curriculum.status);

  return (
    <>
      <PageHeader
        eyebrow="Curriculum Studio"
        title={curriculum.title}
        description={`Version ${curriculum.version_number} · ${curriculum.total_weeks} weeks · ${curriculum.learning_days_per_week} days/week · ${curriculum.hours_per_day} hrs/day · ${formatWorkload(curriculum.units)} total workload`}
        actions={
          <div className="flex items-center gap-2">
            <StatusBadge tone={badge.tone} label={badge.label} />
            <Link
              to={`/document/${curriculum.document_id}`}
              className="inline-flex items-center gap-1 text-xs font-semibold text-oxford-700 hover:text-oxford-800"
            >
              <ArrowLeft className="h-3.5 w-3.5" /> Document
            </Link>
          </div>
        }
      />

      {curriculum.description && (
        <Card className="mb-5">
          <CardContent className="p-4">
            <p className="text-sm text-foreground/80">{curriculum.description}</p>
          </CardContent>
        </Card>
      )}

      <div className="mb-5">
        <ReviewPanel curriculum={curriculum} onUpdated={() => void load()} />
      </div>

      {/* Three-column studio */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[240px_1fr_300px]">
        {/* Left: weeks */}
        <div className="rounded-xl border border-border bg-card p-3 shadow-card lg:h-[calc(100vh-260px)] lg:overflow-hidden lg:sticky lg:top-20">
          <WeekSidebar
            units={curriculum.units}
            selectedWeek={selectedWeek}
            onSelect={setSelectedWeek}
          />
        </div>

        {/* Center: selected week */}
        <div className="min-w-0">
          {selectedUnit ? (
            <div className="space-y-5">
              <WeekCard unit={selectedUnit} />
              <div className="flex flex-wrap items-center gap-x-6 gap-y-1 rounded-xl border border-border bg-card px-4 py-3 text-xs text-muted-foreground shadow-card">
                <span>
                  <strong className="font-semibold text-ink">Total plan workload:</strong>{" "}
                  {formatMinutes(totalMinutes)}
                </span>
                <span className="hidden text-border sm:inline" aria-hidden>
                  ·
                </span>
                <span>
                  avg{" "}
                  <strong className="font-semibold text-ink">
                    {curriculum.units.length > 0
                      ? formatMinutes(Math.round(totalMinutes / curriculum.units.length))
                      : "—"}
                  </strong>{" "}
                  per week
                </span>
              </div>
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-border bg-card py-20 text-center text-sm text-muted-foreground">
              {curriculum.units.length === 0
                ? "This curriculum has no weekly units yet."
                : "Select a week from the sidebar."}
            </div>
          )}
        </div>

        {/* Right: AI context */}
        <div className="lg:h-[calc(100vh-260px)] lg:overflow-y-auto">
          <AIInsightPanel curriculum={curriculum} selectedUnit={selectedUnit} />
        </div>
      </div>
    </>
  );
}