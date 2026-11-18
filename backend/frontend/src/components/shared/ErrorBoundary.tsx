import { Component, type ErrorInfo, type ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { AlertTriangle, RotateCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { isStaff } from "@/lib/auth";

interface ErrorBoundaryInnerProps {
  children: ReactNode;
  /** Rendered instead of the default error card when provided. */
  fallback?: (error: Error, reset: () => void) => ReactNode;
  /** Current router location; a pathname change clears the error. */
  location?: { pathname: string };
}

interface ErrorBoundaryState {
  error: Error | null;
}

class ErrorBoundaryInner extends Component<
  ErrorBoundaryInnerProps,
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error(
      "Unhandled render error:",
      error,
      errorInfo.componentStack ?? "",
    );
  }

  componentDidUpdate(prevProps: ErrorBoundaryInnerProps) {
    // Navigating to another page clears the caught error so the new
    // page renders normally instead of staying on the fallback card.
    const { error } = this.state;
    const { location } = this.props;
    if (
      error !== null &&
      location !== undefined &&
      prevProps.location?.pathname !== location.pathname
    ) {
      this.reset();
    }
  }

  reset = () => {
    this.setState({ error: null });
  };

  render() {
    const { error } = this.state;
    if (error === null) {
      return this.props.children;
    }

    if (this.props.fallback) {
      return this.props.fallback(error, this.reset);
    }

    return (
      <div className="flex min-h-[50vh] flex-col items-center justify-center rounded-2xl border border-dashed border-sand-300 bg-card/60 px-8 py-16 text-center shadow-inset-line">
        <span className="relative mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-brand-50 text-brand ring-8 ring-brand/[0.04]">
          <AlertTriangle className="h-8 w-8" />
        </span>
        <h3 className="font-display text-lg font-semibold tracking-tight text-ink">
          Something went wrong
        </h3>
        <p className="mt-2 max-w-md text-sm leading-relaxed text-muted-foreground">
          Part of this page failed to load. You can try again or return to
          your home page — your session is unaffected.
        </p>
        <p className="mt-1 max-w-md break-all font-mono text-xs text-muted-foreground/70">
          {error.message || "Unknown render error"}
        </p>
        <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
          <Button size="lg" onClick={this.reset}>
            <RotateCw className="mr-1 h-4 w-4" />
            Try again
          </Button>
          <Button asChild variant="outline" size="lg">
            <Link to={isStaff() ? "/dashboard" : "/learn"}>
              Go to home page
            </Link>
          </Button>
        </div>
      </div>
    );
  }
}

/**
 * Contain render failures so a crash in one page cannot blank the whole
 * single-page application: the shells, navigation and session stay alive
 * and the learner/lecturer gets an actionable recovery card instead of a
 * white screen.
 *
 * The boundary resets automatically when the route changes, and manually
 * through the fallback's "Try again" action.
 */
export function ErrorBoundary(props: {
  children: ReactNode;
  fallback?: (error: Error, reset: () => void) => ReactNode;
}) {
  const location = useLocation();
  return (
    <ErrorBoundaryInner location={location} {...props}>
      {props.children}
    </ErrorBoundaryInner>
  );
}
