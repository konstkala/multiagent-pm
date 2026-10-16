"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Alert, Button, TextField } from "@/components/ui";
import { api, call, errorText } from "@/lib/api/client";

export function ResetPasswordForm() {
  const token = useSearchParams().get("token");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) return;
    const form = new FormData(event.currentTarget);
    const password = String(form.get("password"));
    if (password !== String(form.get("confirm"))) {
      setError("The two passwords don't match.");
      return;
    }
    setPending(true);
    setError(null);
    try {
      await call(api.POST("/auth/reset-password", { body: { token, password } }));
      setDone(true);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setPending(false);
    }
  }

  if (!token) {
    return <Alert tone="error">This link is incomplete. Open the link from the email again.</Alert>;
  }
  if (done) {
    return (
      <div className="flex flex-col gap-4">
        <Alert tone="success">Password changed. You&apos;ve been signed out everywhere.</Alert>
        <Link href="/sign-in" className="text-sm text-accent hover:underline">
          Sign in with your new password
        </Link>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-5">
      <h1 className="text-xl font-semibold">Choose a new password</h1>
      {error ? <Alert tone="error">{error}</Alert> : null}
      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        <TextField
          label="New password"
          name="password"
          type="password"
          autoComplete="new-password"
          required
          minLength={10}
          maxLength={128}
          hint="At least 10 characters."
        />
        <TextField label="Repeat it" name="confirm" type="password" autoComplete="new-password" required />
        <Button type="submit" pending={pending}>
          Change password
        </Button>
      </form>
    </div>
  );
}
