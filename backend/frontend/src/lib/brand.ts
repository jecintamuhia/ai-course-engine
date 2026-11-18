/**
 * Single source of truth for SkillUp Action Africa brand values.
 *
 * Colours mirror the tokens published on the official site
 * (skillupafrica.co.ke) so the workspace, the Moodle theme and the
 * certificates stay visually consistent with the organisation.
 */

export const BRAND = {
  /** Full legal name of the organisation. */
  name: "SkillUp Action Africa",
  /** Short form used in tight spaces such as the sidebar. */
  shortName: "SkillUp",
  /** Product descriptor shown under the wordmark. */
  product: "Course Intelligence Workspace",
  /** Public website. */
  website: "https://skillupafrica.co.ke",
  /** Canonical horizontal lockup (official artwork, full resolution). */
  logo: "/brand/skillup-action-africa-logo.png",
  /** Downscaled lockup for navigation and footer placements. */
  logoSmall: "/brand/skillup-action-africa-logo-sm.png",
  /** Symbol only, for square placements and favicons. */
  mark: "/brand/skillup-action-africa-mark.png",
} as const;

export const BRAND_COLORS = {
  red: "#ED1B24",
  redDeep: "#C8131B",
  blue: "#283890",
  blueDeep: "#1E2763",
  dark: "#0D1117",
  background: "#F7F7F7",
  text: "#1A1A2E",
  textMuted: "#5A6270",
  border: "#E4E4E4",
} as const;
