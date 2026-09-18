import type { DraftPreferences } from "@/lib/types";

export const DRAFT_DEFAULTS: DraftPreferences = {
  title: null,
  description: null,
  shortname: null,
  category_id: null,
  total_weeks: 16,
  learning_days_per_week: 5,
};

function keyFor(documentId: string): string {
  return `draft:${documentId}`;
}

export function getDraft(documentId: string): DraftPreferences {
  try {
    const raw = localStorage.getItem(keyFor(documentId));
    if (!raw) return { ...DRAFT_DEFAULTS };
    return { ...DRAFT_DEFAULTS, ...(JSON.parse(raw) as Partial<DraftPreferences>) };
  } catch {
    return { ...DRAFT_DEFAULTS };
  }
}

export function saveDraft(
  documentId: string,
  preferences: Partial<DraftPreferences>,
): void {
  try {
    localStorage.setItem(
      keyFor(documentId),
      JSON.stringify({ ...getDraft(documentId), ...preferences }),
    );
  } catch {
    // localStorage unavailable (private mode / quota) — non-fatal.
  }
}

export function clearDraft(documentId: string): void {
  try {
    localStorage.removeItem(keyFor(documentId));
  } catch {
    // Noop
  }
}