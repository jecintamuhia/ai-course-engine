import { cn } from "@/lib/utils";

/**
 * The official multi-colour Google "G" mark, inlined so sign-in works
 * offline and in air-gapped deployments without loading remote assets.
 */
function GoogleMark({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
    >
      <path
        fill="#4285F4"
        d="M23.52 12.27c0-.85-.08-1.67-.22-2.45H12v4.63h6.46a5.52 5.52 0 0 1-2.4 3.62v3h3.88c2.27-2.09 3.58-5.17 3.58-8.8Z"
      />
      <path
        fill="#34A853"
        d="M12 24c3.24 0 5.96-1.08 7.94-2.91l-3.88-3c-1.08.72-2.45 1.15-4.06 1.15-3.12 0-5.77-2.11-6.71-4.95H1.28v3.1A12 12 0 0 0 12 24Z"
      />
      <path
        fill="#FBBC05"
        d="M5.29 14.29a7.2 7.2 0 0 1 0-4.58v-3.1H1.28a12 12 0 0 0 0 10.78l4.01-3.1Z"
      />
      <path
        fill="#EA4335"
        d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0A12 12 0 0 0 1.28 6.61l4.01 3.1C6.23 6.87 8.88 4.75 12 4.75Z"
      />
    </svg>
  );
}

interface GoogleSignInButtonProps {
  /** Where the API should send the browser to begin the flow. */
  startUrl: string;
  disabled?: boolean;
  className?: string;
  label?: string;
}

/**
 * Starts the Sign in with Google flow.
 *
 * This is a full-page navigation, not fetch: Google redirects back to the
 * API, which then hands the SPA a one-time code. The access token is
 * deliberately never placed in a URL.
 */
export function GoogleSignInButton({
  startUrl,
  disabled = false,
  className,
  label = "Sign in with Google",
}: GoogleSignInButtonProps) {
  return (
    <a
      href={startUrl}
      aria-disabled={disabled || undefined}
      onClick={(event) => {
        if (disabled) {
          event.preventDefault();
        }
      }}
      className={cn(
        "inline-flex w-full items-center justify-center gap-2 rounded-md border border-border bg-card px-4 py-2 text-sm font-medium text-ink shadow-sm transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ai/40",
        disabled && "pointer-events-none opacity-60",
        className,
      )}
    >
      <GoogleMark className="h-4 w-4" />
      {label}
    </a>
  );
}
