import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

import { PageHeader } from "@/components/shared/PageHeader";
import { LoadingState } from "@/components/shared/LoadingState";
import { ErrorState } from "@/components/shared/ErrorState";
import { MoodlePublishPanel } from "@/components/moodle/MoodlePublishPanel";
import { Card, CardContent } from "@/components/ui/card";

import { api } from "@/lib/api";
import type { CurriculumDetailRead } from "@/lib/types";

export function PublishPage() {
  const { id } = useParams<{ id: string }>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [curriculum, setCurriculum] = useState<CurriculumDetailRead | null>(null);

  const load = async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      setCurriculum(await api.getCurriculum(id));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [id]);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!curriculum) return null;

  if (curriculum.status !== "approved" && curriculum.status !== "published") {
    return (
      <>
        <PageHeader eyebrow="Moodle delivery" title="Publish to Moodle" />
        <Card className="border-red-200 bg-red-50">
          <CardContent className="p-5">
            <p className="text-sm text-red-800">
              This curriculum is <strong>{curriculum.status}</strong>. Only{" "}
              <strong>approved</strong> curricula can be published to Moodle.
            </p>
            <Link
              to={`/curriculum/${curriculum.id}`}
              className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-brand-700 hover:text-brand-800"
            >
              <ArrowLeft className="h-4 w-4" /> Back to the curriculum
            </Link>
          </CardContent>
        </Card>
      </>
    );
  }

  return (
    <>
      <PageHeader
        eyebrow="Moodle delivery"
        title="Publish to Moodle"
        description={`Curriculum: ${curriculum.title}`}
      />
      <MoodlePublishPanel curriculum={curriculum} />
    </>
  );
}