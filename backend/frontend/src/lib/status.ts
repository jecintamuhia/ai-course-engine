import type {
  CurriculumStatus,
  CourseStatus,
  IngestionState,
  LessonStatus,
  MoodleConnectionStatus,
} from "@/lib/types";

export type Tone =
  | "neutral"
  | "primary"
  | "success"
  | "warning"
  | "danger"
  | "info"
  | "ai";

export const INGESTION_LABELS: Record<IngestionState, string> = {
  pending: "Queued",
  validating: "Validating",
  extracting: "Extracting text",
  normalizing: "Normalizing",
  structuring: "Detecting structure",
  chunking: "Chunking",
  analyzing: "AI analysis",
  knowledge_building: "Knowledge building",
  planning: "Planning",
  validating_output: "Validating output",
  awaiting_review: "Awaiting review",
  approved: "Approved",
  publishing: "Publishing",
  completed: "Completed",
  failed: "Failed",
  cancelled: "Cancelled",
};

export const CURRICULUM_LABELS: Record<CurriculumStatus, string> = {
  draft: "Draft",
  awaiting_review: "Awaiting review",
  approved: "Approved",
  rejected: "Rejected",
  published: "Published",
};

export const LESSON_LABELS: Record<LessonStatus, string> = {
  draft: "Draft",
  generating: "Generating",
  failed: "Failed",
  awaiting_review: "Awaiting review",
  approved: "Approved",
  rejected: "Rejected",
};

export function ingestionLabel(status: IngestionState | null | undefined): string {
  if (!status) return "Not processed";
  return INGESTION_LABELS[status] ?? status;
}

export function ingestionTone(status: IngestionState | null | undefined): Tone {
  if (!status) return "neutral";
  if (status === "completed") return "success";
  if (status === "failed") return "danger";
  if (status === "cancelled") return "neutral";
  if (status === "pending") return "neutral";
  return "primary";
}

export function curriculumLabel(status: CurriculumStatus): string {
  return CURRICULUM_LABELS[status] ?? status;
}

export function curriculumTone(status: CurriculumStatus): Tone {
  switch (status) {
    case "awaiting_review":
      return "warning";
    case "approved":
      return "success";
    case "rejected":
      return "danger";
    case "published":
      return "primary";
    default:
      return "neutral";
  }
}

export function lessonLabel(status: LessonStatus | null | undefined): string {
  if (!status) return "Draft";
  return LESSON_LABELS[status] ?? status;
}

export function lessonTone(status: LessonStatus | null | undefined): Tone {
  if (!status) return "neutral";
  switch (status) {
    case "approved":
      return "success";
    case "rejected":
    case "failed":
      return "danger";
    case "awaiting_review":
    case "draft":
    case "generating":
      return "warning";
    default:
      return "neutral";
  }
}

export function courseLabel(status: CourseStatus | string): string {
  return status === "synced" || status === "SYNCED" ? "Synced" : status || "Unknown";
}

export function courseTone(status: CourseStatus | string): Tone {
  return status === "synced" || status === "SYNCED" ? "success" : "danger";
}

export function moodleState(status: MoodleConnectionStatus | null): {
  label: string;
  tone: Tone;
} {
  if (!status || !status.configured) {
    return { label: "Moodle: not configured", tone: "neutral" };
  }
  if (status.connected) {
    return { label: `Moodle: ${status.site_name ?? "connected"}`, tone: "success" };
  }
  return { label: "Moodle: disconnected", tone: "danger" };
}

export const INGESTION_STEP_ORDER = [
  "validating",
  "extracting",
  "normalizing",
  "structuring",
  "chunking",
  "analyzing",
] as const satisfies readonly IngestionState[];

export const INGESTION_STEP_LABELS: Record<
  (typeof INGESTION_STEP_ORDER)[number],
  { title: string; description: string }
> = {
  validating: { title: "Validate", description: "Validating the uploaded file" },
  extracting: { title: "Extract text", description: "Extracting pages" },
  normalizing: { title: "Normalize", description: "Normalizing text" },
  structuring: { title: "Detect structure", description: "Detecting chapters & sections" },
  chunking: { title: "Chunk", description: "Building semantic chunks" },
  analyzing: { title: "Analyze with AI", description: "Extracting topics & concepts" },
};

export const TERMINAL_STATES: IngestionState[] = ["completed", "failed", "cancelled"];

export function isActiveJob(status: IngestionState | null | undefined): boolean {
  if (!status) return false;
  return !TERMINAL_STATES.includes(status);
}