import { useEffect, useState } from "react";

import { PageHeader } from "@/components/shared/PageHeader";
import { LoadingState } from "@/components/shared/LoadingState";
import { ErrorState } from "@/components/shared/ErrorState";
import { EmptyState } from "@/components/shared/EmptyState";
import { TextbookTable } from "@/components/textbooks/TextbookTable";

import { api } from "@/lib/api";
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

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <>
      <PageHeader
        title="Documents"
        description={`All uploaded textbooks and their processing progress. ${docs.length} document${docs.length !== 1 && "s"} in library.`}
      />

      {docs.length === 0 ? (
        <EmptyState
          title="No documents found"
          description="Upload a textbook to get started."
          actionLabel="Upload a textbook"
          actionTo="/upload"
        />
      ) : (
        <div className="rounded-lg border border-border bg-card p-4 shadow-sm">
          <TextbookTable documents={docs} />
        </div>
      )}
    </>
  );
}