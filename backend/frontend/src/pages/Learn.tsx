import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  BookOpen,
  CheckCircle2,
  ExternalLink,
  GraduationCap,
  Library,
  Loader2,
  Sparkles,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { LearnerLoading } from "@/components/layout/LearnerShell";
import { api } from "@/lib/api";
import { BRAND } from "@/lib/brand";
import type { LearnerCourseRead, LearnerProfileRead } from "@/lib/types";

function formatDate(value: string | null): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function EnrolledCourseCard({ course }: { course: LearnerCourseRead }) {
  const synced = formatDate(course.last_sync_at);

  return (
    <Card className="flex flex-col">
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <CardTitle className="font-display text-lg text-navy-900">
              {course.title}
            </CardTitle>
            <CardDescription className="mt-1">{course.shortname}</CardDescription>
          </div>
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand/10 text-brand-700">
            <GraduationCap className="h-5 w-5" />
          </span>
        </div>
      </CardHeader>

      <CardContent className="flex flex-1 flex-col justify-end gap-4">
        <dl className="grid grid-cols-2 gap-3 text-xs">
          <div className="rounded-lg bg-sand-100 px-3 py-2">
            <dt className="text-muted-foreground">Sections</dt>
            <dd className="mt-0.5 text-sm font-semibold text-ink">
              {course.sections_published}
            </dd>
          </div>
          <div className="rounded-lg bg-sand-100 px-3 py-2">
            <dt className="text-muted-foreground">Resources</dt>
            <dd className="mt-0.5 text-sm font-semibold text-ink">
              {course.resources_published}
            </dd>
          </div>
        </dl>

        <div className="flex flex-wrap gap-2">
          <Button asChild size="sm">
            <Link to={`/learn/course/${course.id}`}>
              <CheckCircle2 className="h-4 w-4" />
              Lessons &amp; progress
            </Link>
          </Button>
          {course.moodle_url && (
            <Button asChild variant="outline" size="sm">
              <a href={course.moodle_url} target="_blank" rel="noreferrer">
                <BookOpen className="h-4 w-4" />
                Open on Moodle
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            </Button>
          )}
        </div>

        {synced && (
          <p className="text-[11px] text-muted-foreground">
            Last published {synced}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function CatalogCourseCard({
  course,
  busy,
  onEnrol,
}: {
  course: LearnerCourseRead;
  busy: boolean;
  onEnrol: (course: LearnerCourseRead) => void;
}) {
  return (
    <Card className="flex flex-col">
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <CardTitle className="font-display text-lg text-navy-900">
              {course.title}
            </CardTitle>
            <CardDescription className="mt-1">{course.shortname}</CardDescription>
          </div>
          <Badge variant="primary">Available</Badge>
        </div>
      </CardHeader>

      <CardContent className="flex flex-1 flex-col justify-end gap-4">
        <p className="text-sm text-muted-foreground">
          Enrol to open the lessons, mark them complete and hand in the
          practical tasks. Your progress is kept on this portal.
        </p>
        <Button size="sm" disabled={busy} onClick={() => onEnrol(course)}>
          {busy && <Loader2 className="h-4 w-4 animate-spin" />}
          Enrol in this course
        </Button>
      </CardContent>
    </Card>
  );
}

/**
 * Learner home: the account summary, the courses the learner is enrolled
 * in, and the catalogue of courses still open for enrolment.
 *
 * Everything shown here is the learner's own data, read from this
 * application's database. The Moodle link on each course is where the
 * lessons themselves are delivered.
 */
export function LearnPage() {
  const [profile, setProfile] = useState<LearnerProfileRead | null>(null);
  const [courses, setCourses] = useState<LearnerCourseRead[]>([]);
  const [catalog, setCatalog] = useState<LearnerCourseRead[]>([]);
  const [enrolling, setEnrolling] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [profileResponse, courseResponse, catalogResponse] = await Promise.all([
      api.learnerProfile(),
      api.learnerCourses(),
      api.learnerCatalog(),
    ]);
    setProfile(profileResponse);
    setCourses(courseResponse.courses);
    setCatalog(catalogResponse.courses);
  }, []);

  useEffect(() => {
    let active = true;

    load()
      .catch((cause: unknown) => {
        if (!active) return;
        setError(
          cause instanceof Error
            ? cause.message
            : "Could not load your learning plan.",
        );
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [load]);

  async function handleEnrol(course: LearnerCourseRead) {
    setEnrolling(course.id);
    setError(null);
    setNotice(null);
    try {
      await api.learnerEnrol(course.id);
      await load();
      setNotice(`You are now enrolled in ${course.title}.`);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Could not enrol in this course.",
      );
    } finally {
      setEnrolling(null);
    }
  }

  if (loading) return <LearnerLoading />;

  const firstName = (profile?.full_name || profile?.email || "there").split(" ")[0];
  const enrolledIds = new Set(courses.map((course) => course.id));
  const available = catalog.filter((course) => !enrolledIds.has(course.id));

  return (
    <div className="space-y-8">
      <section className="overflow-hidden rounded-2xl bg-navy-950 text-sand-100">
        <div className="relative px-6 py-9 sm:px-9 sm:py-11">
          <span
            aria-hidden
            className="pointer-events-none absolute inset-x-0 top-0 h-56 bg-[radial-gradient(120%_90%_at_18%_-20%,rgba(40,56,144,0.85)_0%,rgba(18,23,56,0)_62%)]"
          />
          <span
            aria-hidden
            className="pointer-events-none absolute inset-x-0 bottom-0 h-56 bg-[radial-gradient(110%_90%_at_85%_120%,rgba(237,27,36,0.28)_0%,rgba(18,23,56,0)_62%)]"
          />
          <div className="relative z-10 max-w-2xl">
            <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-sand-100/55">
              <Sparkles className="h-3.5 w-3.5 text-brand-400" />
              {BRAND.shortName} learning
            </p>
            <h1 className="mt-3 font-display text-3xl font-bold leading-tight text-white sm:text-4xl">
              Welcome back, {firstName}.
            </h1>
            <p className="mt-3 text-sm leading-relaxed text-sand-100/70">
              Enrol in a course, work through its lessons and hand in the
              practical tasks. Course content is delivered on Moodle; your
              progress, marks and feedback stay here on the {BRAND.name} learner
              portal.
            </p>
          </div>
        </div>
      </section>

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

      <section aria-labelledby="learner-courses-heading" className="space-y-4">
        <div>
          <h2
            id="learner-courses-heading"
            className="font-display text-xl font-bold text-navy-900"
          >
            Your courses
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {courses.length === 0
              ? "You have not enrolled in a course yet."
              : `${courses.length} course${courses.length === 1 ? "" : "s"} enrolled in.`}
          </p>
        </div>

        {courses.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
              <span className="flex h-12 w-12 items-center justify-center rounded-full bg-sand-100 text-muted-foreground">
                <Library className="h-6 w-6" />
              </span>
              <div>
                <p className="font-semibold text-ink">Nothing here yet</p>
                <p className="mt-1 max-w-sm text-sm text-muted-foreground">
                  Enrol in one of the published courses below to start working
                  through the lessons.
                </p>
              </div>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {courses.map((course) => (
              <EnrolledCourseCard key={course.id} course={course} />
            ))}
          </div>
        )}
      </section>

      {available.length > 0 && (
        <section aria-labelledby="learner-catalog-heading" className="space-y-4">
          <div>
            <h2
              id="learner-catalog-heading"
              className="font-display text-xl font-bold text-navy-900"
            >
              Open for enrolment
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              {available.length} published course
              {available.length === 1 ? "" : "s"} you have not joined yet.
            </p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {available.map((course) => (
              <CatalogCourseCard
                key={course.id}
                course={course}
                busy={enrolling === course.id}
                onEnrol={handleEnrol}
              />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
