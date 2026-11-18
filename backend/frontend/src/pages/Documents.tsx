import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Layers, Package, Upload, FileText, BookMarked, Library } from "lucide-react";

import { SectionHeader } from "@/components/shared/SectionHeader";
import { LoadingState } from "@/components/shared/LoadingState";
import { ErrorState } from "@/components/shared/ErrorState";
import { EmptyState } from "@/components/shared/EmptyState";
import { TextbookCard } from "@/components/textbooks/TextbookCard";
import { Button } from "@/components/ui/button";

import { api } from "@/lib/api";
import { isActiveJob } from "@/lib/status";
import type { DocumentOverview } from "@/lib/types";

export function DocumentsPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [docs, setDocs] = useState<DocumentOverview[]>([]);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.listDocuments();
      setDocs(res.documents ?? []);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const summary = useMemo(
    () => ({
      count: docs.length,
      pages: docs.reduce((acc, d) => acc + (d.page_count ?? 0), 0),
      topics: docs.reduce((acc, d) => acc + (d.topic_count ?? 0), 0),
      processing: docs.filter((d) =>
        d.latest_job ? isActiveJob(d.latest_job.status) : false,
      ).length,
    }),
    [docs],
  );

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
        <SectionHeader
          icon={<Library className="h-4 w-4" />}
          title="Textbooks"
          description={`Every textbook uploaded to your workspace, with live processing progress. ${docs.length} document${docs.length !== 1 ? "s" : ""} in library.`}
        />
        <Link to="/upload">
          <Button className="h-10">
            <Upload className="h-4 w-4" />
            Upload textbook
          </Button>
        </Link>
      </div>

      {docs.length > 0 && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <LibraryStat icon={Package} value={summary.count} label="Textbooks" />
          <LibraryStat icon={FileText} value={summary.pages} label="Pages" />
          <LibraryStat icon={BookMarked} value={summary.topics} label="Topics" />
          <LibraryStat
            icon={Layers}
            value={summary.processing}
            label="In progress"
            live={summary.processing > 0}
          />
        </div>
      )}

      {docs.length === 0 ? (
        <EmptyState
          title="No textbooks yet"
          description="Upload a textbook to start the intelligence pipeline. The engine extracts structure, plans a curriculum and prepares it for Moodle."
          actionLabel="Upload your first textbook"
          actionTo="/upload"
        />
      ) : (
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {docs.map((doc) => (
            <TextbookCard key={doc.document.id} doc={doc} />
          ))}
        </div>
      )}
    </div>
  );
}

function LibraryStat({
  icon: Icon,
  value,
  label,
  live,
}: {
  icon: typeof Upload;
  value: number;
  label: string;
  live?: boolean;
}) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-border bg-card px-4 py-3 shadow-card">
      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-50 text-brand">
        <Icon className="h-4 w-4" />
      </div>
      <div>
        <div className="tnum text-lg font-bold leading-none text-ink">
          {value}
          {live && (
            <span className="ml-1.5 inline-block h-1.5 w-1.5 animate-pulse-soft rounded-full bg-brand align-middle" />
          )}
        </div>
        <div className="mt-1 text-[11px] font-medium text-muted-foreground">{label}</div>
      </div>
    </div>
  );
}