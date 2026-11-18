import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, ArrowRight, ExternalLink } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { SafeHtml } from "@/components/shared/SafeHtml";
import { api } from "@/lib/api";
import { isStaff } from "@/lib/auth";
import type {
  MoodleCourseStructureRead,
  MoodleModuleRead,
} from "@/lib/types";

/**
 * Lecturer view of a published course's curriculum.
 *
 * Read-only: the lecturer sees the curriculum published to Moodle (weeks,
 * sections, lessons) and can open any lesson's content inside the SkillUp
 * Action Africa portal. No Moodle administrator privileges are required
 * and the user is never sent to the Moodle administration site.
 */
export function LecturerCoursePage() {
  const { courseId = "", lessonId = "" } = useParams();
  const navigate = useNavigate();
  const [structure, setStructure] = useState<MoodleCourseStructureRead | null>(
    null,
  );
  const [content, setContent] = useState<{
    title: string;
    content_html: string;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadStructure = useCallback(async () => {
    const result = await api.lecturerCourseContent(courseId);
    setStructure(result);
  }, [courseId]);

  const loadLesson = useCallback(async () => {
    const result = await api.lecturerLessonContent(courseId, lessonId);
    setContent({ title: result.title, content_html: result.content_html });
  }, [courseId, lessonId]);

  useEffect(() => {
    let active = true;
    loadStructure()
      .catch((cause: unknown) => {
        if (!active) return;
        setError(
          cause instanceof Error
            ? cause.message
            : "Could not open this course.",
        );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [loadStructure]);

  useEffect(() => {
    if (!lessonId) return;
    let active = true;
    loadLesson()
      .catch((cause: unknown) => {
        if (!active) return;
        setError(
          cause instanceof Error
            ? cause.message
            : "Could not open this lesson.",
        );
      });
    return () => {
      active = false;
    };
  }, [loadLesson, lessonId]);

  async function handleRetryStructure() {
    setError(null);
    setLoading(true);
    try {
      await loadStructure();
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Could not open this course.",
      );
    } finally {
      setLoading(false);
    }
  }

  if (!isStaff()) {
    return (
      <div className="space-y-4">
        <p className="text-sm text-brand-800">
          This view is restricted to lecturers and administrators.
        </p>
        <Button asChild variant="outline" size="sm">
          <Link to="/dashboard">
            <ArrowLeft className="h-4 w-4" />
            Back to dashboard
          </Link>
        </Button>
      </div>
    );
  }

  if (loading) return <div className="py-16 text-center text-muted-foreground">Loading course…</div>;

  if (!structure) {
    return (
      <div className="space-y-4">
        <p className="text-sm text-brand-800">
          {error || "This course could not be opened."}
        </p>
        {error && (
          <Button
            variant="outline"
            size="sm"
            onClick={handleRetryStructure}
          >
            Try again
          </Button>
        )}
        <Button asChild variant="outline" size="sm">
          <Link to="/reviews">
            <ArrowLeft className="h-4 w-4" />
            Back to review
          </Link>
        </Button>
      </div>
    );
  }

  const allModules: MoodleModuleRead[] = [];
  structure.sections.forEach((section) => {
    section.modules.forEach((module) => {
      if (module.modname === "page" && module.lesson_id) {
        allModules.push(module);
      }
    });
  });

  const currentModuleIndex = lessonId
    ? allModules.findIndex((m) => m.lesson_id === lessonId)
    : -1;
  const prevModule = currentModuleIndex > 0 ? allModules[currentModuleIndex - 1] : null;
  const nextModule =
    currentModuleIndex >= 0 && currentModuleIndex < allModules.length - 1
      ? allModules[currentModuleIndex + 1]
      : null;

  const openLesson = (module: MoodleModuleRead) => {
    if (!module.lesson_id) return;
    navigate(`/lecturer/courses/${courseId}/lessons/${module.lesson_id}`);
  };

  async function handleRetryLesson() {
    setError(null);
    if (!lessonId) return;
    try {
      await loadLesson();
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Could not open this lesson.",
      );
    }
  }

  return (
    <div className="space-y-7">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Button asChild variant="ghost" size="sm" className="-ml-2">
          <Link to="/reviews">
            <ArrowLeft className="h-4 w-4" />
            Back to review
          </Link>
        </Button>
        {structure.moodle_url && (
          <Button asChild variant="outline" size="sm">
            <a href={structure.moodle_url} target="_blank" rel="noreferrer">
              View on Moodle
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
          </Button>
        )}
      </div>

      <section className="overflow-hidden rounded-2xl bg-navy-950 text-sand-100">
        <div className="relative px-6 py-8 sm:px-9">
          <div className="relative z-10 flex flex-wrap items-end justify-between gap-4">
            <div className="max-w-2xl">
              <h1 className="font-display text-2xl font-bold text-white sm:text-3xl">
                {structure.title}
              </h1>
              <p className="mt-2 text-sm text-sand-100/70">
                Published course &middot; {structure.sections.length} week
                {structure.sections.length === 1 ? "" : "s"}
              </p>
            </div>
          </div>
        </div>
      </section>

      {error && (
        <div className="rounded-lg border border-brand/30 bg-brand/5 px-4 py-3 text-sm text-brand-800">
          {error}
          {lessonId && (
            <Button
              variant="outline"
              size="sm"
              className="ml-4"
              onClick={handleRetryLesson}
            >
              Try again
            </Button>
          )}
        </div>
      )}

      {content ? (
        <>
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setContent(null)}
            >
              <ArrowLeft className="h-4 w-4" />
              Curriculum
            </Button>
            <div className="flex items-center gap-2">
              {prevModule && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setContent(null);
                    navigate(
                      `/lecturer/courses/${courseId}/lessons/${prevModule.lesson_id}`,
                    );
                  }}
                >
                  Previous lesson
                </Button>
              )}
              {nextModule && (
                <Button
                  size="sm"
                  variant="default"
                  onClick={() => {
                    setContent(null);
                    navigate(
                      `/lecturer/courses/${courseId}/lessons/${nextModule.lesson_id}`,
                    );
                  }}
                >
                  Next lesson
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              )}
            </div>
            <Progress
              className="relative z-10 mt-2 bg-navy-800"
              value={100}
              aria-label="Lesson content"
            />
          </div>
          <Card className="overflow-hidden">
            <CardHeader>
              <CardTitle className="font-display text-base text-navy-900">
                {content.title}
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <SafeHtml
                className="prose prose-sm max-w-none p-6 text-ink"
                html={content.content_html}
              />
            </CardContent>
          </Card>
        </>
      ) : (
        <>
          {structure.sections.map((section) => (
            <section key={section.section_number} className="space-y-3">
              <h2 className="font-display text-lg font-bold text-navy-900">
                Week {section.section_number}
              </h2>
              <p className="text-sm text-muted-foreground">
                {section.name}
              </p>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {section.modules
                  .filter((module) => module.modname === "page")
                  .map((module) => (
                    <Card key={module.cmid}>
                      <CardHeader>
                        <CardTitle className="font-display text-base text-navy-900">
                          {module.name || "Lesson"}
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="pt-1">
                        {module.lesson_id ? (
                          <Button
                            size="sm"
                            variant="default"
                            onClick={() => openLesson(module)}
                          >
                            Open lesson
                          </Button>
                        ) : (
                          <Button size="sm" variant="outline" disabled>
                            Content not available
                          </Button>
                        )}
                      </CardContent>
                    </Card>
                  ))}
              </div>
            </section>
          ))}
          {allModules.length === 0 && (
            <Card>
              <CardContent className="py-10 text-center text-sm text-muted-foreground">
                No lessons have been published for this course yet.
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
