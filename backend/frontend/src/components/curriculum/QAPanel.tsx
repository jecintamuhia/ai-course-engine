import { useCallback, useEffect, useState } from "react";
import { ClipboardCheck, FileQuestion, RefreshCw, ScrollText } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { api } from "@/lib/api";
import { formatMinutes } from "@/lib/format";
import type {
  AssessmentRead,
  AssessmentType,
  CoverageReportRead,
  CurriculumDetailRead,
  CurriculumUnitRead,
  QAReportRead,
} from "@/lib/types";
import { toast } from "sonner";
import type { Tone } from "@/lib/status";

interface QAPanelProps {
  curriculum: CurriculumDetailRead;
  selectedUnit: CurriculumUnitRead | null;
  onUpdated: () => void;
}

const VERDICT_TONES: Record<string, Tone> = {
  pass: "success",
  warning: "warning",
  fail: "danger",
};

const SEVERITY_TONES: Record<string, string> = {
  error: "bg-red-100 text-red-800",
  warning: "bg-amber-100 text-amber-800",
  info: "bg-slate-100 text-slate-700",
};

const AREA_LABELS: Record<string, string> = {
  coverage: "Coverage",
  duplication: "Duplication",
  provenance: "Provenance",
  quality: "Quality / depth",
  learning_design: "Learning design",
  moodle: "Moodle readiness",
};

export function QAPanel({ curriculum, selectedUnit, onUpdated }: QAPanelProps) {
  const [report, setReport] = useState<QAReportRead | null>(null);
  const [qaLoading, setQaLoading] = useState(false);
  const [coverageLoading, setCoverageLoading] = useState(false);
  const [coverage, setCoverage] = useState<CoverageReportRead | null>(null);
  const [assessments, setAssessments] = useState<AssessmentRead[]>([]);
  const [assessmentLoading, setAssessmentLoading] = useState(false);

  const loadReport = useCallback(async () => {
    try {
      setReport(await api.getQualityReport(curriculum.id));
    } catch {
      setReport(null);
    }
  }, [curriculum.id]);

  const loadAssessments = useCallback(async () => {
    try {
      const response = await api.listCurriculumAssessments(curriculum.id);
      setAssessments(response.assessments);
    } catch {
      setAssessments([]);
    }
  }, [curriculum.id]);

  useEffect(() => {
    void loadReport();
    void loadAssessments();
  }, [loadReport, loadAssessments]);

  const runQA = async () => {
    setQaLoading(true);
    try {
      const response = await api.runQA(curriculum.id);
      setReport(response.report);
      toast.success(
        response.blocked
          ? "QA found blocking issues."
          : `QA passed${response.report.verdict === "warning" ? " with warnings." : "."}`,
      );
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setQaLoading(false);
    }
  };

  const loadCoverage = async () => {
    setCoverageLoading(true);
    try {
      setCoverage(await api.getCoverageReport(curriculum.id));
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setCoverageLoading(false);
    }
  };

  const generateUnitAssessment = async (assessmentType?: AssessmentType) => {
    if (!selectedUnit) return;
    setAssessmentLoading(true);
    try {
      await api.generateUnitAssessment(curriculum.id, selectedUnit.id, {
        assessment_type: assessmentType ?? null,
      });
      toast.success(`Assessment generated for ${selectedUnit.title}.`);
      await loadAssessments();
      onUpdated();
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setAssessmentLoading(false);
    }
  };

  const generateFinal = async () => {
    setAssessmentLoading(true);
    try {
      await api.generateFinalAssessment(curriculum.id);
      toast.success("Final assessment generated.");
      await loadAssessments();
      onUpdated();
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setAssessmentLoading(false);
    }
  };

  const reviewAssessment = async (assessment: AssessmentRead, decision: "approved" | "rejected") => {
    try {
      await api.reviewAssessment(assessment.id, { decision });
      toast.success(`Assessment ${decision === "approved" ? "approved" : "rejected"}.`);
      await loadAssessments();
    } catch (err) {
      toast.error((err as Error).message);
    }
  };

  return (
    <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
      {/* Content QA */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <ClipboardCheck className="h-4 w-4 text-ai" /> Content QA
          </CardTitle>
          <Button size="sm" variant="outline" onClick={runQA} disabled={qaLoading}>
            <RefreshCw className={`mr-1 h-3.5 w-3.5 ${qaLoading ? "animate-spin" : ""}`} />
            {qaLoading ? "Running…" : "Run QA"}
          </Button>
        </CardHeader>
        <CardContent className="space-y-4">
          {report ? (
            <>
              <div className="flex flex-wrap items-center gap-3">
                <StatusBadge tone={VERDICT_TONES[report.verdict] ?? "neutral"} label={report.verdict} />
                <span className="text-xs text-muted-foreground">
                  v{report.version_number} · {report.findings.length} findings ·{" "}
                  {new Date(report.checked_at).toLocaleString()}
                </span>
              </div>

              {Object.keys(report.areas).length > 0 && (
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                  {Object.entries(report.areas).map(([area, status]) => (
                    <div
                      key={area}
                      className="rounded-lg border border-border px-3 py-2 text-xs"
                    >
                      <div className="font-medium text-foreground">{AREA_LABELS[area] ?? area}</div>
                      <div className="mt-0.5 flex items-center gap-1.5">
                        <StatusBadge tone={VERDICT_TONES[status.status] ?? "neutral"} label={status.status} dot={false} />
                        <span className="text-muted-foreground">({status.findings})</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {report.findings.length > 0 && (
                <ul className="max-h-72 space-y-2 overflow-y-auto pr-1">
                  {report.findings.map((finding, index) => (
                    <li
                      key={`${finding.rule}-${finding.code}-${index}`}
                      className="rounded-lg border border-border bg-muted/30 px-3 py-2"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <p className="text-xs font-medium text-foreground">{finding.message}</p>
                        <span className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase ${SEVERITY_TONES[finding.severity]}`}>
                          {finding.severity}
                        </span>
                      </div>
                      {finding.locations.length > 0 && (
                        <p className="mt-1 text-[11px] text-muted-foreground">
                          {finding.locations
                            .map((loc) => [loc.title, loc.detail].filter(Boolean).join(" · "))
                            .join("; ")}
                        </p>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </>
          ) : (
            <p className="text-xs text-muted-foreground">
              No QA report yet. Run QA to check coverage, provenance, depth, and learning design
              before approving or publishing.
            </p>
          )}

          <div className="border-t border-border pt-3">
            <Button size="sm" variant="outline" onClick={loadCoverage} disabled={coverageLoading}>
              <ScrollText className="mr-1 h-3.5 w-3.5" />
              {coverageLoading ? "Loading…" : "Show coverage report"}
            </Button>
            {coverage && (
              <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs sm:grid-cols-3">
                <StatItem label="Coverage" value={`${coverage.coverage_percent}%`} />
                <StatItem label="Topics" value={`${coverage.mapped_topic_count}/${coverage.topic_count}`} />
                <StatItem label="Lessons" value={String(coverage.lesson_count)} />
                <StatItem label="Chapters" value={String(coverage.chapters)} />
                <StatItem label="Duplicates removed" value={String(coverage.duplicate_topics_removed)} />
                <StatItem label="Resources / videos" value={`${coverage.resource_count} / ${coverage.video_count}`} />
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Assessments */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <FileQuestion className="h-4 w-4 text-ai" /> Assessments
          </CardTitle>
          <div className="flex gap-2">
            {selectedUnit && (
              <Button
                size="sm"
                variant="outline"
                disabled={assessmentLoading}
                onClick={() => generateUnitAssessment()}
              >
                Generate for {selectedUnit.title}
              </Button>
            )}
            <Button size="sm" variant="outline" disabled={assessmentLoading} onClick={generateFinal}>
              Generate final
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {assessments.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              No assessments yet. Generate one for a weekly unit (grounded in its textbook chunks
              and aligned to its learning objectives) or a course final.
            </p>
          ) : (
            <ul className="max-h-72 space-y-3 overflow-y-auto pr-1">
              {assessments.map((assessment) => (
                <li key={assessment.id} className="rounded-lg border border-border p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-medium text-foreground">{assessment.title}</span>
                        <StatusBadge
                          tone={assessment.status === "approved" ? "success" : assessment.status === "rejected" ? "danger" : "warning"}
                          label={assessment.status}
                          dot={false}
                        />
                      </div>
                      <p className="mt-0.5 text-[11px] text-muted-foreground">
                        {assessment.assessment_type.replace(/_/g, " ")}
                        {assessment.week_number ? ` · week ${assessment.week_number}` : " · course final"} ·{" "}
                        {assessment.items.length} items · {formatMinutes(assessment.estimated_minutes)}
                      </p>
                    </div>
                    <div className="flex shrink-0 gap-1.5">
                      {assessment.status === "awaiting_review" && (
                        <>
                          <Button size="sm" variant="success" onClick={() => reviewAssessment(assessment, "approved")}>
                            Approve
                          </Button>
                          <Button size="sm" variant="destructive" onClick={() => reviewAssessment(assessment, "rejected")}>
                            Reject
                          </Button>
                        </>
                      )}
                    </div>
                  </div>
                  {assessment.alignment.length > 0 && (
                    <p className="mt-2 text-[11px] text-muted-foreground">
                      Aligned objectives:{" "}
                      {assessment.alignment
                        .map((a) => a.lesson_title ?? a.learning_objective)
                        .filter(Boolean)
                        .join(" · ")}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function StatItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-muted-foreground">{label}</div>
      <div className="font-semibold text-ink">{value === "" ? "—" : value}</div>
    </div>
  );
}