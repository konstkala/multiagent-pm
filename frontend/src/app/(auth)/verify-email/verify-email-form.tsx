"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { Alert, Button } from "@/components/ui";
import { api, call, errorText } from "@/lib/api/client";

export function VerifyEmailForm() {
  const token = useSearchParams().get("token");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  // A button, not an automatic request: email scanners open links, and the token works once.
  async function confirm() {
    if (!token) return;
    setPending(true);
    setError(null);
    try {
      await call(api.POST("/auth/verify-email", { body: { token } }));
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
  return (
    <div className="flex flex-col gap-5">
      <h1 className="text-xl font-semibold">Confirm your email</h1>
      {error ? <Alert tone="error">{error}</Alert> : null}
      {done ? (
        <>
          <Alert tone="success">Email confirmed. You can sign in now.</Alert>
          <Link href="/sign-in" className="text-sm text-link hover:underline">
            Sign in
          </Link>
        </>
      ) : (
        <Button onClick={confirm} pending={pending}>
          Confirm my email address
        </Button>
      )}
    </div>
  );
}
