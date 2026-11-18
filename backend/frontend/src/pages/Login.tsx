import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Loader2, LogIn } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AuthShell } from "@/components/auth/AuthShell";
import { GoogleSignInButton } from "@/components/auth/GoogleSignInButton";
import { api, ApiError } from "@/lib/api";
import { beginSession, isAbsoluteUrl } from "@/lib/session";
import type { AuthMethods } from "@/lib/types";

function applyDestination(destination: string, navigate: ReturnType<typeof useNavigate>) {
  if (isAbsoluteUrl(destination)) {
    window.location.assign(destination);
  } else {
    navigate(destination, { replace: true });
  }
}

export function LoginPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [exchanging, setExchanging] = useState(false);
  const [methods, setMethods] = useState<AuthMethods | null>(null);

  // Which sign-in options the server actually offers. Hiding an
  // unconfigured method beats showing a button that cannot work.
  useEffect(() => {
    let active = true;
    api
      .authMethods()
      .then((response) => {
        if (active) setMethods(response);
      })
      .catch(() => {
        if (active) setMethods(null);
      });
    return () => {
      active = false;
    };
  }, []);

  // Google redirects back here with a single-use code. Exchange it for the
  // token immediately so the access token never enters a URL or history.
  useEffect(() => {
    const code = searchParams.get("code");
    const authError = searchParams.get("auth_error");

    if (authError) {
      toast.error(authError);
      setSearchParams({}, { replace: true });
      return;
    }

    if (!code) return;

    let active = true;
    setExchanging(true);
    api
      .exchangeGoogleCode(code)
      .then((response) => {
        if (!active) return;
        const destination = beginSession(response);
        toast.success(`Welcome, ${response.user.full_name || response.user.email}.`);
        applyDestination(destination, navigate);
      })
      .catch((error: unknown) => {
        if (!active) return;
        toast.error(
          error instanceof ApiError
            ? error.message
            : "Could not complete Google sign-in.",
        );
        setSearchParams({}, { replace: true });
      })
      .finally(() => {
        if (active) setExchanging(false);
      });

    return () => {
      active = false;
    };
  }, [searchParams, setSearchParams, navigate]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!email.trim() || !password) {
      toast.error("Enter both your email address and password.");
      return;
    }
    setSubmitting(true);
    try {
      const response = await api.login(email, password);
      const destination = beginSession(response);
      toast.success(`Welcome back, ${response.user.full_name || response.user.email}.`);
      applyDestination(destination, navigate);
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Sign-in failed. Try again.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  const googleEnabled = methods?.google_enabled ?? false;
  const registrationEnabled = methods?.registration_enabled ?? false;
  const busy = submitting || exchanging;

  return (
    <AuthShell
      title="Sign in"
      subtitle="Learners, lecturers and administrators of SkillUp Action Africa."
    >
      <Card>
        <CardContent className="p-6">
          {googleEnabled && (
            <>
              <GoogleSignInButton
                startUrl={api.googleStartUrl()}
                disabled={busy}
              />
              {methods?.allowed_domains?.length ? (
                <p className="mt-2 text-center text-[11px] text-muted-foreground">
                  Or use {methods.allowed_domains.join(", ")} email
                </p>
              ) : null}
              <div className="my-5 flex items-center gap-3">
                <span className="h-px flex-1 bg-border" />
                <span className="text-[11px] uppercase tracking-wide text-muted-foreground">
                  or
                </span>
                <span className="h-px flex-1 bg-border" />
              </div>
            </>
          )}

          {exchanging ? (
            <div className="flex items-center justify-center gap-2 py-6 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Completing Google sign-in…
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="login-email">Email address</Label>
                <Input
                  id="login-email"
                  type="email"
                  autoComplete="username"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  required
                  autoFocus
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="login-password">Password</Label>
                <Input
                  id="login-password"
                  type="password"
                  autoComplete="current-password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                />
              </div>

              <Button type="submit" className="mt-1 w-full" disabled={busy}>
                {submitting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Signing in…
                  </>
                ) : (
                  <>
                    <LogIn className="h-4 w-4" />
                    Sign in
                  </>
                )}
              </Button>
            </form>
          )}
        </CardContent>
      </Card>

      <div className="mt-6 space-y-3 text-center text-xs text-muted-foreground">
        {registrationEnabled && (
          <p>
            New here?{" "}
            <Link
              to="/register"
              className="font-semibold text-brand-700 hover:text-brand-800"
            >
              Create a learner account
            </Link>
          </p>
        )}

        <p>Authenticated access is required to view course content.</p>
      </div>
    </AuthShell>
  );
}
