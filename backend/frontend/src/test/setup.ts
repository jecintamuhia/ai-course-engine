/**
 * Test-environment shims for jsdom: some browser APIs used by Radix UI
 * components (and indirectly by the pages under test) are missing in
 * jsdom and must be polyfilled before any component renders.
 *
 * Testing Library's automatic cleanup only registers itself when test
 * globals are on; with vitest's explicit imports it must be wired here.
 */

import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(cleanup);

if (typeof window.matchMedia !== "function") {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => undefined,
      removeListener: () => undefined,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      dispatchEvent: () => false,
    }),
  });
}
