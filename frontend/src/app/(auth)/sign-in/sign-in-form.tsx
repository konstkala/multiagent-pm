"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { Alert, Button, TextField } from "@/components/ui";
import { ApiError, api, call, errorText } from "@/lib/api/client";
import { safeNextPath } from "@/lib/navigation";

export function SignInForm() {
  const router = useRouter();
  const params = useSearchParams();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(
    params.get("error") === "google" ? "Google sign-in didn't complete. Try again." : null,
  );
  const [unverifiedEmail, setUnverifiedEmail] = useState<string | null>(null);
  const [resent, setResent] = useState(false);
  const [googleEnabled, setGoogleEnabled] = useState(false);

  useEffect(() => {
    call(api.GET("/auth/providers")).then(
      (providers) => setGoogleEnabled(providers.google),
      () => setGoogleEnabled(false),
    );
  }, []);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email"));
    setPending(true);
    setError(null);
    setUnverifiedEmail(null);
    try {
      await call(
        api.POST("/auth/sign-in", { body: { email, password: String(form.get("password")) } }),
      );
      router.replace(safeNextPath(params.get("next")));
    } catch (err) {
      if (err instanceof ApiError && err.code === "email_not_verified") setUnverifiedEmail(email);
      setError(errorText(err));
      setPending(false);
    }
  }

  async function resend() {
    if (!unverifiedEmail) return;
    try {
      await call(api.POST("/auth/resend-verification", { body: { email: unverifiedEmail } }));
      setResent(true);
    } catch (err) {
      setError(errorText(err));
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <h1 className="text-xl font-semibold">Sign in</h1>
      {error ? <Alert tone="error">{error}</Alert> : null}
      {unverifiedEmail && !resent ? (
        <Button type="button" variant="secondary" onClick={resend}>
          Send the confirmation email again
        </Button>
      ) : null}
      {resent ? <Alert tone="success">Confirmation email sent. Check your inbox.</Alert> : null}

      {googleEnabled ? (
        <>
          {/* A full page navigation: the browser must visit Google, not fetch it. */}
          <a
            href="/api/auth/google/start"
            className="lift inline-flex items-center justify-center rounded-full border border-control bg-surface px-4 py-2 text-sm font-medium hover:bg-subtle"
          >
            Continue with Google
          </a>
          <p className="text-center text-xs text-muted">or use your email</p>
        </>
      ) : null}

      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        <TextField label="Email" name="email" type="email" autoComplete="email" required />
        <TextField
          label="Password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
        />
        <Button type="submit" pending={pending}>
          Sign in
        </Button>
      </form>

      <div className="flex justify-between text-sm">
        <Link href="/forgot-password" className="text-link hover:underline">
          Forgot password?
        </Link>
        <Link href="/sign-up" className="text-link hover:underline">
          Create an account
        </Link>
      </div>
    </div>
  );
}
