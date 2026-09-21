import { Database, BrainCircuit, Workflow } from "lucide-react";

import type { SourceType } from "@/lib/types";

const SOURCE_META: Record<
  SourceType,
  { label: string; className: string; icon: typeof Database }
> = {
  source_derived: {
    label: "Source-derived",
    className: "border-emerald-200 bg-emerald-50 text-emerald-800",
    icon: Database,
  },
  ai_generated: {
    label: "AI-generated",
    className: "border-ai/25 bg-ai/10 text-ai",
    icon: BrainCircuit,
  },
  ai_enriched: {
    label: "AI-enriched",
    className: "border-sky-200 bg-sky-50 text-sky-800",
    icon: Workflow,
  },
};

interface SourceBadgeProps {
  sourceType?: SourceType | string | null;
  className?: string;
}

export function SourceBadge({ sourceType, className }: SourceBadgeProps) {
  if (!sourceType) return null;
  const meta = SOURCE_META[sourceType as SourceType];
  if (!meta) return null;
  const Icon = meta.icon;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[10px] font-semibold ${meta.className} ${className ?? ""}`}
      title={`Provenance: ${meta.label}`}
    >
      <Icon className="h-3 w-3" />
      {meta.label}
    </span>
  );
}