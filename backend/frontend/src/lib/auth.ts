import type { UserRole } from "@/lib/types";

const TOKEN_KEY = "ace_access_token";

const STAFF_ROLES: readonly UserRole[] = ["admin", "lecturer"];

const LEARNER_ROLES: readonly UserRole[] = ["student", "teacher"];

function normalizeRole(value: unknown): UserRole | null {
  return value === "admin" ||
    value === "lecturer" ||
    value === "student" ||
    value === "teacher"
    ? value
    : null;
}

function decodeRole(token: string): UserRole | null {
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  try {
    const normalized = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const payload = JSON.parse(atob(normalized)) as { role?: unknown };
    return normalizeRole(payload.role);
  } catch {
    return null;
  }
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export function isAuthenticated(): boolean {
  return Boolean(getToken());
}

/** Role carried by the current token, or null when absent/unreadable. */
export function getRole(): UserRole | null {
  const token = getToken();
  return token ? decodeRole(token) : null;
}

/** Whether the current account may use the authoring workspace. */
export function isStaff(): boolean {
  const role = getRole();
  return role !== null && STAFF_ROLES.includes(role);
}

/** Whether the current account uses the learner portal. */
export function isLearner(): boolean {
  const role = getRole();
  return role !== null && LEARNER_ROLES.includes(role);
}
