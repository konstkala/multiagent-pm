"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";

import { Alert, Button, TextField } from "@/components/ui";
import { api, call, errorText } from "@/lib/api/client";

export function ForgotPasswordForm() {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const email = String(new FormData(event.currentTarget).get("email"));
    setPending(true);
    setError(null);
    try {
      setDone((await call(api.POST("/auth/forgot-password", { body: { email } }))).message);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <h1 className="text-xl font-semibold">Reset your password</h1>
      {done ? (
        <Alert tone="success">{done}</Alert>
      ) : (
        <>
          <p className="text-sm text-muted">
            Enter your email and we&apos;ll send you a link to choose a new password.
          </p>
          {error ? <Alert tone="error">{error}</Alert> : null}
          <form onSubmit={onSubmit} className="flex flex-col gap-4">
            <TextField label="Email" name="email" type="email" autoComplete="email" required />
            <Button type="submit" pending={pending}>
              Send reset link
            </Button>
          </form>
        </>
      )}
      <Link href="/sign-in" className="text-sm text-accent hover:underline">
        Back to sign in
      </Link>
    </div>
  );
}
