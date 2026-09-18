import type { CurriculumUnitRead } from "@/lib/types";

export function formatBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let index = 0;
  let value = bytes;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  return `${value.toFixed(value >= 10 || index === 0 ? 0 : 1)} ${units[index]}`;
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatMinutes(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined) return "—";
  const hours = Math.round((minutes / 60) * 10) / 10;
  return `${hours} h`;
}

export function formatWorkload(units: CurriculumUnitRead[]): string {
  if (!units || units.length === 0) return "—";
  const total = units.reduce(
    (acc, unit) => acc + (unit.estimated_workload_minutes || 0),
    0,
  );
  return formatMinutes(total);
}

export function stripExtension(name: string | null | undefined): string | null {
  if (!name) return name ?? null;
  const idx = name.lastIndexOf(".");
  return idx > 0 ? name.slice(0, idx) : name;
}

export function ordinalWeek(week: number): string {
  return String(week).padStart(2, "0");
}