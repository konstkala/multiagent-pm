"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Alert, Button, TextField } from "@/components/ui";
import { api, call, errorText } from "@/lib/api/client";

export function SignUpForm() {
  const invitedEmail = useSearchParams().get("email") ?? undefined;
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setPending(true);
    setError(null);
    try {
      const result = await call(
        api.POST("/auth/sign-up", {
          body: {
            display_name: String(form.get("display_name")),
            email: String(form.get("email")),
            password: String(form.get("password")),
          },
        }),
      );
      setDone(result.message);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setPending(false);
    }
  }

  if (done) {
    return (
      <div className="flex flex-col gap-4">
        <h1 className="text-xl font-semibold">Check your inbox</h1>
        <Alert tone="success">{done}</Alert>
        <p className="text-sm text-muted">
          Open the link in the email to confirm your address, then sign in.
        </p>
        <Link href="/sign-in" className="text-sm text-link hover:underline">
          Back to sign in
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <h1 className="text-xl font-semibold">Create your account</h1>
      {error ? <Alert tone="error">{error}</Alert> : null}
      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        <TextField label="Your name" name="display_name" autoComplete="name" required maxLength={100} />
        <TextField
          label="Email"
          name="email"
          type="email"
          autoComplete="email"
          required
          defaultValue={invitedEmail}
        />
        <TextField
          label="Password"
          name="password"
          type="password"
          autoComplete="new-password"
          required
          minLength={10}
          maxLength={128}
          hint="At least 10 characters. A few random words work well."
        />
        <Button type="submit" pending={pending}>
          Create account
        </Button>
      </form>
      <p className="text-sm text-muted">
        Already have an account?{" "}
        {/* Underlined: inside a sentence, colour alone isn't enough to tell a link apart. */}
        <Link href="/sign-in" className="text-link underline underline-offset-2">
          Sign in
        </Link>
      </p>
    </div>
  );
}
