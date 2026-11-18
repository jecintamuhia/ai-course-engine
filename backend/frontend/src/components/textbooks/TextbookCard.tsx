import { Link } from "react-router-dom";
import { FileText, Calendar, Layers, ArrowRight, Hash } from "lucide-react";
import { useMemo } from "react";

import { Card, CardContent } from "@/components/ui/card";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { ingestBadge } from "@/lib/badges";
import { formatBytes, formatDateShort } from "@/lib/format";
import { INGESTION_STEP_ORDER, isActiveJob } from "@/lib/status";
import { cn } from "@/lib/utils";
import type { DocumentOverview } from "@/lib/types";

interface TextbookCardProps {
  doc: DocumentOverview;
}

export function TextbookCard({ doc }: TextbookCardProps) {
  const badge = useMemo(
    () => ingestBadge(doc.latest_job ? doc.latest_job.status : null),
    [doc.latest_job],
  );

  const progress = useMemo(() => {
    const job = doc.latest_job;
    if (!job) return 0;
    if (job.status === "completed") return 100;
    if (job.status === "failed" || job.status === "cancelled") return 100;
    const idx = INGESTION_STEP_ORDER.indexOf(
      job.status as (typeof INGESTION_STEP_ORDER)[number],
    );
    return idx >= 0 ? Math.min(100, Math.round(((idx + 1) / INGESTION_STEP_ORDER.length) * 100)) : 0;
  }, [doc.latest_job]);

  const busy = useMemo(
    () => doc.latest_job != null && isActiveJob(doc.latest_job.status),
    [doc.latest_job],
  );

  return (
    <Card className="group flex h-full flex-col transition-all hover:-translate-y-0.5 hover:border-brand/30 hover:shadow-lift">
      <CardContent className="flex flex-1 flex-col p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand ring-4 ring-brand/[0.04]">
            <FileText className="h-5 w-5" />
          </div>
          <StatusBadge tone={badge.tone} label={badge.label} />
        </div>

        <Link
          to={`/document/${doc.document.id}`}
          className="mt-4 block text-[15px] font-semibold leading-snug text-ink transition-colors hover:text-brand-700"
          title={doc.document.original_filename}
        >
          <span className="line-clamp-2">{doc.document.original_filename}</span>
        </Link>

        <div className="mt-1.5 flex items-center gap-2 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1">
            <Hash className="h-3 w-3" />
            {formatBytes(doc.document.size_bytes)}
          </span>
          <span aria-hidden>·</span>
          <span className="inline-flex items-center gap-1">
            <Calendar className="h-3 w-3" />
            {formatDateShort(doc.document.created_at)}
          </span>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-2 border-t border-border pt-4">
          <MiniStat value={doc.page_count} label="Pages" />
          <MiniStat value={doc.chunk_count} label="Chunks" />
          <MiniStat value={doc.topic_count} label="Topics" toneOut="text-brand" />
          <MiniStat value={doc.curriculum_count} label="Curricula" />
        </div>

        {/* Processing indicator */}
        {(doc.latest_job || doc.topic_count > 0) && (
          <div className="mt-4">
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-secondary">
              <div
                className={cn(
                  "h-full rounded-full transition-all duration-700",
                  doc.latest_job?.status === "failed"
                    ? "bg-red-500"
                    : doc.latest_job?.status === "completed" ||
                        doc.latest_job?.status === "approved"
                      ? "bg-emerald-500"
                      : "bg-brand",
                )}
                style={{ width: `${progress}%` }}
              />
            </div>
            <div className="mt-1.5 flex items-center justify-between text-[10px] text-muted-foreground">
              <span>
                {busy
                  ? "Processing in background…"
                  : doc.latest_job?.status === "failed"
                    ? "Pipeline failed — check the workspace"
                    : `${progress}% through the pipeline`}
              </span>
              <span className="tnum">{progress}%</span>
            </div>
          </div>
        )}

        <Link
          to={`/document/${doc.document.id}`}
          className="mt-auto inline-flex items-center gap-1 pt-4 text-xs font-semibold text-brand-700 transition-colors hover:text-brand-800"
        >
          <Layers className="h-3.5 w-3.5" />
          Open analysis workspace
          <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
        </Link>
      </CardContent>
    </Card>
  );
}

function MiniStat({
  value,
  label,
  toneOut,
}: {
  value: number;
  label: string;
  toneOut?: string;
}) {
  return (
    <div className="rounded-lg bg-sand-100/60 px-2.5 py-2 text-center">
      <div className={cn("tnum text-base font-bold text-ink", toneOut)}>{value ?? 0}</div>
      <div className="text-[10px] font-medium text-muted-foreground">{label}</div>
    </div>
  );
}