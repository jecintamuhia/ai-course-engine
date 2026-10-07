import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Loader2, UserPlus } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { GoogleSignInButton } from "@/components/auth/GoogleSignInButton";
import { api } from "@/lib/api";
import { setToken } from "@/lib/auth";
import type { AuthMethods } from "@/lib/types";

export function RegisterPage() {
  const navigate = useNavigate();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [methods, setMethods] = useState<AuthMethods | null>(null);

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

  // The server is the authority on whether sign-ups are open.
  useEffect(() => {
    if (methods && !methods.registration_enabled) {
      toast.error("Registration is disabled on this server.");
      navigate("/login", { replace: true });
    }
  }, [methods, navigate]);

  const allowedDomains = methods?.allowed_domains ?? [];
  const emailHint =
    allowedDomains.length > 0
      ? `Use your ${allowedDomains.join(" or ")} address`
      : undefined;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!fullName.trim() || !email.trim() || !password) {
      toast.error("Complete every field to create your account.");
      return;
    }
    if (password.length < 8) {
      toast.error("Your password must be at least 8 characters.");
      return;
    }
    if (password !== confirmPassword) {
      toast.error("The two passwords do not match.");
      return;
    }

    setSubmitting(true);
    try {
      const response = await api.register({
        email: email.trim(),
        password,
        full_name: fullName.trim(),
      });
      setToken(response.access_token);
      toast.success(`Welcome, ${response.user.full_name}. Your account is ready.`);
      navigate("/dashboard", { replace: true });
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Could not create your account.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-svh items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center">
          <h1 className="text-xl font-bold tracking-tight text-ink">
            Create your account
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Lecturer access to the course intelligence workspace
          </p>
        </div>

        <Card>
          <CardContent className="p-6">
            {methods?.google_enabled && (
              <>
                <GoogleSignInButton
                  startUrl={api.googleStartUrl()}
                  disabled={submitting}
                  label="Continue with Google"
                />
                <div className="my-5 flex items-center gap-3">
                  <span className="h-px flex-1 bg-border" />
                  <span className="text-[11px] uppercase tracking-wide text-muted-foreground">
                    or
                  </span>
                  <span className="h-px flex-1 bg-border" />
                </div>
              </>
            )}

            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="register-name">Full name</Label>
                <Input
                  id="register-name"
                  type="text"
                  autoComplete="name"
                  placeholder="Jane Doe"
                  value={fullName}
                  onChange={(event) => setFullName(event.target.value)}
                  required
                  autoFocus
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="register-email">Email address</Label>
                <Input
                  id="register-email"
                  type="email"
                  autoComplete="email"
                  placeholder="you@gmail.com"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  required
                />
                {emailHint && (
                  <p className="text-[11px] text-muted-foreground">{emailHint}</p>
                )}
              </div>

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="register-password">Password</Label>
                <Input
                  id="register-password"
                  type="password"
                  autoComplete="new-password"
                  placeholder="At least 8 characters"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                  minLength={8}
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <Label htmlFor="register-confirm">Confirm password</Label>
                <Input
                  id="register-confirm"
                  type="password"
                  autoComplete="new-password"
                  placeholder="Repeat your password"
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  required
                  minLength={8}
                />
              </div>

              <Button type="submit" className="mt-1 w-full" disabled={submitting}>
                {submitting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Creating account…
                  </>
                ) : (
                  <>
                    <UserPlus className="h-4 w-4" />
                    Create account
                  </>
                )}
              </Button>
            </form>
          </CardContent>
        </Card>

        <p className="mt-6 text-center text-xs text-muted-foreground">
          Already have an account?{" "}
          <Link
            to="/login"
            className="font-semibold text-burgundy-700 hover:text-burgundy-800"
          >
            Sign in
          </Link>
        </p>
        <p className="mt-2 text-center text-[11px] text-muted-foreground">
          New accounts are lecturers. Administrator access is granted by an
          existing administrator.
        </p>
      </div>
    </div>
  );
}
