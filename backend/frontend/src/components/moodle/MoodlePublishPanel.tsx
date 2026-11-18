import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { curriculumBadge, courseBadge } from "@/lib/badges";
import { formatDate } from "@/lib/format";
import { getDraft } from "@/lib/drafts";
import { api, ApiError } from "@/lib/api";
import { toast } from "sonner";
import type {
  CurriculumDetailRead,
  MoodleCourseRead,
  MoodlePreflightCheck,
  MoodlePreflightResponse,
  MoodlePublishResponse,
} from "@/lib/types";
import {
  AlertTriangle,
  CheckCircle,
  Download,
  ExternalLink,
  Loader2,
  RefreshCw,
  ShieldAlert,
  XCircle,
} from "lucide-react";

interface MoodlePublishPanelProps {
  curriculum: CurriculumDetailRead;
}

function ReadinessChecks({ checks }: { checks: MoodlePreflightCheck[] }) {
  return (
    <ul className="mt-3 space-y-1.5">
      {checks.map((check) => (
        <li key={check.label} className="flex items-start gap-2 text-xs">
          {check.status === "ok" ? (
            <CheckCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600" />
          ) : check.status === "error" ? (
            <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-600" />
          ) : (
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-500" />
          )}
          <span className="min-w-0 flex-1">
            <span className="font-medium text-ink">{check.label}</span>
            <span className="text-muted-foreground">
              {" "}
              — {check.status === "ok" ? "OK" : check.detail}
            </span>
            {check.verification !== "direct" && (
              <span className="mt-0.5 block text-[10px] text-muted-foreground">
                {check.verification === "inferred"
                  ? "Inferred from declared web service functions — capabilities are not directly queryable via the Moodle API."
                  : "Not verifiable through the Moodle API."}
              </span>
            )}
          </span>
        </li>
      ))}
    </ul>
  );
}

export function MoodlePublishPanel({ curriculum }: MoodlePublishPanelProps) {
  const draft = getDraft(curriculum.document_id);
  const badge = curriculumBadge(curriculum.status);

  const [fullname, setFullname] = useState(curriculum.title);
  const [shortname, setShortname] = useState(draft.shortname ?? "");
  const [categoryId, setCategoryId] = useState(String(draft.category_id ?? 1));
  const [idnumber, setIdnumber] = useState(`ai-ece-${curriculum.id}`);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<MoodlePublishResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [preflight, setPreflight] = useState<MoodlePreflightResponse | null>(null);
  const [preflightLoading, setPreflightLoading] = useState(true);

  // Publication state for this curriculum, derived from the existing
  // Course record (never a second state machine): undefined = loading,
  // null = never published, otherwise the stored Moodle course row.
  const [publication, setPublication] = useState<MoodleCourseRead | null | undefined>(
    undefined,
  );

  const refreshPublication = useCallback(() => {
    api
      .listCourses()
      .then((res) => {
        const match = (res.courses ?? []).find(
          (course) => course.curriculum_id === curriculum.id,
        );
        setPublication(match ?? null);
      })
      .catch(() => setPublication(null));
  }, [curriculum.id]);

  const loadPreflight = async () => {
    setPreflightLoading(true);
    try {
      setPreflight(await api.moodlePreflight());
    } catch (err) {
      setPreflight(null);
      toast.error(
        err instanceof ApiError
          ? err.message
          : "Moodle readiness could not be checked.",
      );
    } finally {
      setPreflightLoading(false);
    }
  };

  useEffect(() => {
    void loadPreflight();
    refreshPublication();
  }, [curriculum.id, refreshPublication]);

  const handlePublish = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await api.publishCurriculum(curriculum.id, {
        fullname: fullname.trim() || undefined,
        shortname: shortname.trim() || undefined,
        category_id: Number(categoryId) || undefined,
        idnumber: idnumber.trim() || undefined,
      });
      setResult(res);
      refreshPublication();
      toast.success(`Published: ${res.course_fullname}`);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : (err as Error).message;
      setError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async () => {
    try {
      const payload = await api.exportCurriculum(curriculum.id);
      const blob = new Blob([JSON.stringify(payload, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `curriculum-${curriculum.id}.moodle-export.json`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      toast.success("Moodle-ready export downloaded");
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.message : "Export could not be downloaded.",
      );
    }
  };

  const ready = preflight?.ready === true;

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">Curriculum</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <ul className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
            {(
              [
                ["Generated", true],
                ["Reviewed", curriculum.status !== "draft"],
                [
                  "Approved",
                  ["approved", "published"].includes(curriculum.status),
                ],
              ] as const
            ).map(([label, done]) => (
              <li key={label} className="flex items-center gap-1.5">
                {done ? (
                  <CheckCircle className="h-3.5 w-3.5 text-emerald-600" />
                ) : (
                  <XCircle className="h-3.5 w-3.5 text-muted-foreground/30" />
                )}
                {label}
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm">Publication status</CardTitle>
            {publication ? (
              <StatusBadge {...courseBadge(publication.status)} />
            ) : publication === null ? (
              <StatusBadge tone="neutral" label="Not published" dot={false} />
            ) : (
              <StatusBadge tone="neutral" label="Checking…" dot={false} />
            )}
          </div>
        </CardHeader>
        <CardContent className="pt-0 text-sm">
          {publication === undefined ? (
            <p className="text-muted-foreground">Checking publication state…</p>
          ) : publication === null ? (
            <p className="text-muted-foreground">
              This curriculum has not been published to Moodle yet.
              {ready
                ? " Use “Publish now” below to create the Moodle course."
                : " Resolve the readiness issues below before publishing."}
            </p>
          ) : publication.status === "sync_failed" ? (
            <div className="space-y-1">
              <p className="font-medium text-red-700">
                Publication failed — the last sync did not complete.
              </p>
              {publication.sync_error && (
                <p className="text-xs text-red-700">{publication.sync_error}</p>
              )}
              <p className="text-xs text-muted-foreground">
                Moodle course id {publication.moodle_course_id ?? "—"} · last sync{" "}
                {formatDate(publication.last_sync_at)}. Re-publishing resumes the
                sync idempotently without duplicating content.
              </p>
            </div>
          ) : (
            <div className="space-y-1">
              <p className="font-medium text-emerald-700">Published to Moodle.</p>
              <p className="text-xs text-muted-foreground">
                Moodle course id {publication.moodle_course_id ?? "—"} ·{" "}
                {publication.sections_published} sections ·{" "}
                {publication.resources_published} page resources · last sync{" "}
                {formatDate(publication.last_sync_at)}.
              </p>
              {publication.moodle_url && (
                <a
                  href={publication.moodle_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-sm font-semibold text-brand-700 hover:underline"
                >
                  Open course in Moodle
                  <ExternalLink className="h-3.5 w-3.5" />
                </a>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {preflightLoading ? (
        <Card>
          <CardContent className="p-5 text-sm text-muted-foreground">
            <Loader2 className="mr-2 inline h-4 w-4 animate-spin" />
            Checking Moodle readiness…
          </CardContent>
        </Card>
      ) : preflight === null ? (
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="p-5 text-sm text-amber-900">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 shrink-0 text-amber-600" />
              <strong>Moodle readiness could not be checked.</strong>
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => void loadPreflight()}
              className="mt-3"
            >
              <RefreshCw className="mr-1.5 h-4 w-4" /> Re-check
            </Button>
          </CardContent>
        </Card>
      ) : ready ? (
        <Card className="border-emerald-200 bg-emerald-50">
          <CardContent className="p-5">
            <div className="flex items-start gap-3">
              <CheckCircle className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
              <div className="min-w-0 flex-1">
                <h4 className="text-sm font-semibold text-emerald-900">
                  Moodle is ready to publish
                </h4>
                <p className="mt-1 text-sm text-emerald-800">
                  Connected to{" "}
                  <strong>{preflight.site_name ?? "Moodle"}</strong>
                  {preflight.site_url ? ` (${preflight.site_url})` : ""} ·{" "}
                  {preflight.functions_available.length} required web
                  service function(s) available · category{" "}
                  <strong>{preflight.category_id}</strong> found.
                </p>
                <ReadinessChecks checks={preflight.checks} />
              </div>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="p-5">
            <div className="flex items-start gap-3">
              <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
              <div className="min-w-0 flex-1">
                <h4 className="text-sm font-semibold text-amber-900">
                  Moodle administrator action required
                </h4>
                <p className="mt-1 text-sm text-amber-800">
                  Publishing to Moodle is blocked until the web service is
                  configured. The curriculum has not been modified. Required
                  capabilities:{" "}
                  <strong>{preflight.capabilities_required.join(", ")}</strong>.
                </p>
                <ReadinessChecks checks={preflight.checks} />
                <ul className="mt-3 space-y-2">
                  {preflight.issues.map((issue, index) => (
                    <li
                      key={`${issue.kind}-${index}`}
                      className="rounded-md border border-amber-200 bg-white/60 p-3"
                    >
                      <div className="flex flex-wrap items-center gap-2 text-xs">
                        <StatusBadge tone="warning" label={issue.kind} dot={false} />
                        {issue.ws_function && (
                          <code className="rounded bg-amber-100 px-1.5 py-0.5 text-amber-900">
                            {issue.ws_function}
                          </code>
                        )}
                        {issue.capability && (
                          <code className="rounded bg-amber-100 px-1.5 py-0.5 text-amber-900">
                            {issue.capability}
                          </code>
                        )}
                      </div>
                      <p className="mt-1.5 text-sm text-amber-900">{issue.message}</p>
                      <p className="mt-1 text-xs text-amber-700">
                        <strong>Admin action:</strong> {issue.admin_action}
                      </p>
                    </li>
                  ))}
                </ul>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => void loadPreflight()}
                  className="mt-3"
                >
                  <RefreshCw className="mr-1.5 h-4 w-4" /> Re-check
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-50 text-brand ring-4 ring-brand/[0.04]">
                <ExternalLink className="h-4 w-4" />
              </span>
              <div>
                <CardTitle className="text-sm">Publish to Moodle</CardTitle>
                <div className="text-[11px] text-muted-foreground">
                  Course delivery platform{" "}
                  {preflight?.site_url
                    ?.replace(/^https?:\/\//, "")
                    .replace(/\/$/, "") ?? "—"}
                </div>
              </div>
            </div>
            <StatusBadge tone={badge.tone} label={badge.label} />
          </div>
        </CardHeader>
        <CardContent>
          <form onSubmit={handlePublish} className="space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="fullname">Moodle full name</Label>
                <Input
                  id="fullname"
                  value={fullname}
                  onChange={(e) => setFullname(e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="shortname">Moodle short name</Label>
                <Input
                  id="shortname"
                  value={shortname}
                  onChange={(e) => setShortname(e.target.value)}
                  placeholder="Defaults to the idnumber"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="category">Course category id</Label>
                <Input
                  id="category"
                  type="number"
                  min="1"
                  value={categoryId}
                  onChange={(e) => setCategoryId(e.target.value)}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="idnumber">Moodle idnumber</Label>
                <Input
                  id="idnumber"
                  value={idnumber}
                  onChange={(e) => setIdnumber(e.target.value)}
                  placeholder="ai-ece-…"
                />
                <p className="text-[11px] text-muted-foreground">
                  Idempotent find-or-create: publishing twice reuses the same Moodle course.
                </p>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3 pt-2">
              <Button
                type="submit"
                disabled={loading || !ready}
                variant="default"
              >
                {loading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Publishing…
                  </>
                ) : ready ? (
                  "Publish now"
                ) : (
                  "Publishing unavailable"
                )}
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => void handleExport()}
              >
                <Download className="mr-2 h-4 w-4" />
                Download export (Moodle-ready reference)
              </Button>
            </div>
            {!ready && !loading && (
              <p className="text-xs text-muted-foreground">
                Fix the readiness issues above before publishing. You can still
                download the Moodle-ready course export.
              </p>
            )}
          </form>
        </CardContent>
      </Card>

      {result && (
        <Card className="border-emerald-200 bg-emerald-50">
          <CardContent className="p-5">
            <div className="flex items-start gap-3">
              <CheckCircle className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
              <div className="min-w-0 flex-1">
                <h4 className="text-sm font-semibold text-emerald-900">Published successfully</h4>
                <p className="mt-0.5 text-sm text-emerald-800">
                  Moodle course <strong>{result.course_fullname}</strong> (id {result.moodle_course_id}).
                  {result.created ? " Course was created." : " Existing course reused."}
                </p>
                <p className="mt-1 text-xs text-emerald-700">
                  {result.sections_published} sections · {result.resources_published} page resources ·
                  verified: {result.verified ? "yes" : "no"}
                </p>
                <a
                  href={result.course_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-2 inline-flex items-center gap-1.5 text-sm font-semibold text-emerald-700 hover:text-emerald-900"
                >
                  Open course in Moodle
                  <ExternalLink className="h-3.5 w-3.5" />
                </a>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="p-5 text-sm text-red-800">
            <strong>Publishing failed:</strong> {error}
          </CardContent>
        </Card>
      )}
    </div>
  );
}