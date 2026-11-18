import { isStaff, setToken } from "@/lib/auth";
import type { TokenResponse } from "@/lib/types";

/** True when the destination is an absolute (off-site) URL. */
export function isAbsoluteUrl(value: string): boolean {
  return /^https?:\/\//i.test(value);
}

/**
 * Persist the access token and return the server-decided destination.
 *
 * The server owns the decision: authoring roles land on a same-origin
 * workspace path, learner roles on the learner portal. The fallback used
 * when the server sends no destination mirrors that split, so a client
 * that never receives a ``redirect_to`` still lands somewhere sensible.
 * The caller is responsible for applying the redirect (in-app
 * navigation vs. a full page load).
 */
export function beginSession(response: TokenResponse): string {
  setToken(response.access_token);
  return response.redirect_to || (isStaff() ? "/dashboard" : "/learn");
}
