import { useState, type ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useNavigate } from "react-router-dom";

import { ErrorBoundary } from "@/components/shared/ErrorBoundary";

/** A component that throws during render only while `boom` is true. */
function Bomb({ boom, message = "kaboom" }: { boom: boolean; message?: string }) {
  if (boom) throw new Error(message);
  return <p>All good</p>;
}

function renderWithRouter(ui: ReactNode, { route = "/" } = {}) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <Routes>
        <Route path="/" element={ui} />
      </Routes>
    </MemoryRouter>,
  );
}

/** The boom switch lives OUTSIDE the boundary so it stays usable while the
 * fallback card is shown, mirroring a shell above a crashing page. */
function Harness() {
  const [boom, setBoom] = useState(true);
  return (
    <div>
      <button type="button" onClick={() => setBoom((value) => !value)}>
        flip
      </button>
      <ErrorBoundary>
        <Bomb boom={boom} />
      </ErrorBoundary>
    </div>
  );
}

function NavigationHarness() {
  const navigate = useNavigate();
  return (
    <div>
      <ErrorBoundary>
        <Routes>
          <Route path="/" element={<Bomb boom />} />
          <Route path="/healthy" element={<Bomb boom={false} />} />
        </Routes>
      </ErrorBoundary>
      <button type="button" onClick={() => navigate("/healthy")}>
        navigate away
      </button>
    </div>
  );
}

describe("ErrorBoundary", () => {
  it("renders children while nothing throws", () => {
    renderWithRouter(
      <ErrorBoundary>
        <Bomb boom={false} />
      </ErrorBoundary>,
    );

    expect(screen.getByText("All good")).toBeTruthy();
  });

  it("catches a render error and shows the recovery card", () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => undefined);

    renderWithRouter(
      <ErrorBoundary>
        <Bomb boom />
      </ErrorBoundary>,
    );

    expect(screen.getByText("Something went wrong")).toBeTruthy();
    expect(screen.getByText("kaboom")).toBeTruthy();
    expect(screen.getByRole("button", { name: /try again/i })).toBeTruthy();

    consoleSpy.mockRestore();
  });

  it("offers a home-page link to learners when not staff", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);

    renderWithRouter(
      <ErrorBoundary>
        <Bomb boom />
      </ErrorBoundary>,
    );

    const home = screen.getByRole("link", { name: /go to home page/i });
    expect(home.getAttribute("href")).toBe("/learn");

    vi.restoreAllMocks();
  });

  it("offers a home-page link to the dashboard when staff", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    // A signed-in lecturer token with role "lecturer".
    window.localStorage.setItem(
      "ace_access_token",
      `header.${btoa(JSON.stringify({ role: "lecturer" }))}.signature`,
    );

    try {
      renderWithRouter(
        <ErrorBoundary>
          <Bomb boom />
        </ErrorBoundary>,
      );

      const home = screen.getByRole("link", { name: /go to home page/i });
      expect(home.getAttribute("href")).toBe("/dashboard");
    } finally {
      window.localStorage.clear();
      vi.restoreAllMocks();
    }
  });

  it("recovers via Try again once the underlying cause is gone", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);

    render(
      <MemoryRouter>
        <Harness />
      </MemoryRouter>,
    );

    expect(screen.getByText("Something went wrong")).toBeTruthy();

    // Fix the cause, then retry: the page content comes back.
    fireEvent.click(screen.getByRole("button", { name: "flip" }));
    fireEvent.click(screen.getByRole("button", { name: /try again/i }));

    expect(screen.getByText("All good")).toBeTruthy();

    vi.restoreAllMocks();
  });

  it("stays on the fallback while the cause persists", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);

    render(
      <MemoryRouter>
        <Harness />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("button", { name: /try again/i }));

    expect(screen.getByText("Something went wrong")).toBeTruthy();

    vi.restoreAllMocks();
  });

  it("clears the caught error when the route changes", async () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);

    render(
      <MemoryRouter>
        <NavigationHarness />
      </MemoryRouter>,
    );

    expect(screen.getByText("Something went wrong")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "navigate away" }));

    await waitFor(() => {
      expect(screen.getByText("All good")).toBeTruthy();
    });

    vi.restoreAllMocks();
  });

  it("uses the custom fallback when provided", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);

    renderWithRouter(
      <ErrorBoundary
        fallback={(error, reset) => (
          <button type="button" onClick={reset}>
            custom:{error.message}
          </button>
        )}
      >
        <Bomb boom message="custom boom" />
      </ErrorBoundary>,
    );

    expect(screen.getByText("custom:custom boom")).toBeTruthy();

    vi.restoreAllMocks();
  });
});
