import { Link } from "react-router-dom";
import { FileText, HardDrive, ArrowRight } from "lucide-react";
import { useMemo } from "react";

import { Card, CardContent } from "@/components/ui/card";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { ingestBadge } from "@/lib/badges";
import { formatBytes, formatDate } from "@/lib/format";
import type { DocumentOverview } from "@/lib/types";

interface TextbookCardProps {
  doc: DocumentOverview;
}

export function TextbookCard({ doc }: TextbookCardProps) {
  const badge = useMemo(() => {
    const job = doc.latest_job;
    return ingestBadge(job ? job.status : null);
  }, [doc.latest_job]);

  return (
    <Card className="transition-all hover:border-burgundy/40 hover:shadow-md">
      <CardContent className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-burgundy-50 text-burgundy">
            <FileText className="h-5 w-5" />
          </div>
          <StatusBadge tone={badge.tone} label={badge.label} />
        </div>

        <Link
          to={`/document/${doc.document.id}`}
          className="mt-3 block text-sm font-semibold text-foreground hover:text-burgundy-700"
          title={doc.document.original_filename}
        >
          <span className="line-clamp-2">{doc.document.original_filename}</span>
        </Link>

        <div className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground">
          <HardDrive className="h-3.5 w-3.5" />
          {formatBytes(doc.document.size_bytes)}
          <span aria-hidden>·</span>
          <span>{formatDate(doc.document.created_at)}</span>
        </div>

        <div className="mt-4 grid grid-cols-3 gap-2 border-t border-border pt-3 text-center">
          <MiniStat value={doc.page_count} label="Pages" />
          <MiniStat value={doc.chunk_count} label="Chunks" />
          <MiniStat value={doc.topic_count} label="Topics" />
        </div>

        <Link
          to={`/document/${doc.document.id}`}
          className="mt-4 inline-flex items-center gap-1 text-xs font-semibold text-burgundy-700 hover:text-burgundy-800"
        >
          Open workspace
          <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </CardContent>
    </Card>
  );
}

function MiniStat({ value, label }: { value: number; label: string }) {
  return (
    <div>
      <div className="text-base font-bold text-foreground">{value ?? 0}</div>
      <div className="text-[11px] text-muted-foreground">{label}</div>
    </div>
  );
}