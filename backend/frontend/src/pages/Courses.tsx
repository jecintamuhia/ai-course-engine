import { useEffect, useState } from "react";
import { ExternalLink, RotateCw, BookOpen } from "lucide-react";
import { toast } from "sonner";

import { PageHeader } from "@/components/shared/PageHeader";
import { LoadingState } from "@/components/shared/LoadingState";
import { ErrorState } from "@/components/shared/ErrorState";
import { EmptyState } from "@/components/shared/EmptyState";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";

import { api } from "@/lib/api";
import { courseBadge } from "@/lib/badges";
import { formatDate } from "@/lib/format";
import type { MoodleCourseRead, MoodleVerifyResponse } from "@/lib/types";

export function CoursesPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [courses, setCourses] = useState<MoodleCourseRead[]>([]);
  const [verifyResult, setVerifyResult] = useState<MoodleVerifyResponse | null>(null);
  const [verifyingId, setVerifyingId] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.listCourses();
      setCourses(res.courses ?? []);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const handleVerify = async (courseId: string) => {
    setVerifyingId(courseId);
    setVerifyResult(null);
    try {
      const result = await api.verifyCourse(courseId);
      setVerifyResult(result);
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setVerifyingId(null);
    }
  };

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <>
      <PageHeader
        eyebrow="Moodle delivery"
        title="Published courses"
        description={`${courses.length} course${courses.length !== 1 && "s"} published to Moodle.`}
      />

      {courses.length === 0 ? (
        <EmptyState
          title="No courses on Moodle yet"
          description="Start from a document, generate a curriculum, review it, then publish."
          actionLabel="Browse documents"
          actionTo="/documents"
        />
      ) : (
        <div className="rounded-xl border border-border bg-card p-2 shadow-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Course</TableHead>
                <TableHead>Moodle id</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Sections</TableHead>
                <TableHead className="text-right">Resources</TableHead>
                <TableHead>Last sync</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {courses.map((course) => {
                const badge = courseBadge(course.status);
                return (
                  <TableRow key={course.id}>
                    <TableCell>
                      <div className="flex items-center gap-3">
                        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand ring-4 ring-brand/[0.04]">
                          <BookOpen className="h-3.5 w-3.5" />
                        </span>
                        <div>
                          <div className="font-medium text-foreground">{course.title}</div>
                          <div className="text-[11px] text-muted-foreground">
                            {course.shortname}
                            {course.sync_error && (
                              <span className="ml-2 text-red-600">{course.sync_error}</span>
                            )}
                          </div>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {course.moodle_course_id != null ? course.moodle_course_id : "—"}
                    </TableCell>
                    <TableCell>
                      <StatusBadge {...badge} />
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {course.sections_published}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {course.resources_published}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatDate(course.last_sync_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={verifyingId === course.id}
                          onClick={() => handleVerify(course.id)}
                        >
                          <RotateCw
                            className={`h-3.5 w-3.5 ${verifyingId === course.id ? "animate-spin" : ""}`}
                          />
                          {verifyingId === course.id ? "Checking…" : "Verify"}
                        </Button>
                        {course.moodle_url && (
                          <Button asChild variant="ghost" size="sm">
                            <a href={course.moodle_url} target="_blank" rel="noopener noreferrer">
                              Open
                              <ExternalLink className="h-3.5 w-3.5" />
                            </a>
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}

      <Dialog
        open={verifyResult !== null}
        onOpenChange={(open) => {
          if (!open) setVerifyResult(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Verification result</DialogTitle>
            <DialogDescription>Read-only check against the live Moodle site.</DialogDescription>
          </DialogHeader>
          {verifyResult && (
            <div className="space-y-3">
              {!verifyResult.found ? (
                <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
                  Course not found in Moodle.
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <VerifyStat label="Moodle course id" value={verifyResult.moodle_course_id} />
                  <VerifyStat label="Sections found" value={verifyResult.sections_found} />
                  <VerifyStat label="Modules found" value={verifyResult.modules_found} />
                  <div>
                    <div className="text-[11px] text-muted-foreground">URL</div>
                    {verifyResult.course_url ? (
                      <a
                        href={verifyResult.course_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-medium text-brand-700 hover:underline"
                      >
                        Open ↗
                      </a>
                    ) : (
                      "—"
                    )}
                  </div>
                </div>
              )}
              {verifyResult.section_names.length > 0 && (
                <div>
                  <div className="mb-1.5 text-[11px] font-medium text-muted-foreground uppercase">
                    Sections
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {verifyResult.section_names.map((name) => (
                      <span
                        key={name}
                        className="inline-block rounded-md border border-brand/20 bg-brand-50 px-2 py-0.5 text-xs text-brand-800"
                      >
                        {name}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {verifyResult.error && (
                <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-xs text-red-800">
                  {verifyResult.error}
                </div>
              )}
              <div className="flex justify-end gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setVerifyResult(null)}
                >
                  Close
                </Button>
                {verifyResult.course_url && (
                  <Button asChild variant="default" size="sm">
                    <a href={verifyResult.course_url} target="_blank" rel="noopener noreferrer">
                      Open course
                      <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                  </Button>
                )}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}

function VerifyStat({ label, value }: { label: string; value: number | null }) {
  return (
    <div>
      <div className="text-[11px] text-muted-foreground">{label}</div>
      <div className="font-semibold">{value ?? "—"}</div>
    </div>
  );
}