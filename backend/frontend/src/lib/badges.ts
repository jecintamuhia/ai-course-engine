import type { CurriculumStatus, CourseStatus, IngestionState } from "@/lib/types";
import {
  courseLabel,
  courseTone,
  curriculumLabel,
  curriculumTone,
  ingestionLabel,
  ingestionTone,
  type Tone,
} from "@/lib/status";

export function ingestBadge(status: IngestionState | null | undefined): {
  tone: Tone;
  label: string;
} {
  return { tone: ingestionTone(status), label: ingestionLabel(status) };
}

export function curriculumBadge(status: CurriculumStatus): {
  tone: Tone;
  label: string;
} {
  return { tone: curriculumTone(status), label: curriculumLabel(status) };
}

export function courseBadge(status: CourseStatus | string): {
  tone: Tone;
  label: string;
} {
  return { tone: courseTone(status), label: courseLabel(status) };
}