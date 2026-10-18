"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Alert, Button, Loading } from "@/components/ui";
import { ApiError, api, call, errorText, type Schemas, type User } from "@/lib/api/client";

type Preview = Schemas["InvitationPreviewRead"];

export function InviteView() {
  const token = useSearchParams().get("token");
  const router = useRouter();
  const [preview, setPreview] = useState<Preview | null>(null);
  const [me, setMe] = useState<User | null>(null);
  const [loading, setLoading] = useState(Boolean(token));
  const [error, setError] = useState<string | null>(null);
  const [accepting, setAccepting] = useState(false);

  useEffect(() => {
    if (!token) return;
    Promise.all([
      call(api.POST("/invitations/preview", { body: { token } })),
      // Not signed in is a normal state here, not an error.
      call(api.GET("/auth/me")).catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 401) return null;
        throw err;
      }),
    ]).then(
      ([invitation, user]) => {
        setPreview(invitation);
        setMe(user);
        setLoading(false);
      },
      (err: unknown) => {
        setError(errorText(err));
        setLoading(false);
      },
    );
  }, [token]);

  async function accept() {
    if (!token) return;
    setAccepting(true);
    setError(null);
    try {
      const { project_id } = await call(api.POST("/invitations/accept", { body: { token } }));
      router.replace(`/projects/${project_id}`);
    } catch (err) {
      setError(errorText(err));
      setAccepting(false);
    }
  }

  if (!token) return <Alert tone="error">This link is incomplete. Open the link from the email again.</Alert>;
  if (loading) return <Loading />;
  if (!preview) return <Alert tone="error">{error ?? "This invitation can't be found."}</Alert>;

  const here = `/invite?token=${encodeURIComponent(token)}`;
  return (
    <div className="flex flex-col gap-5">
      <h1 className="text-xl font-semibold">Join {preview.project_name}</h1>
      <p className="text-sm text-muted">
        {preview.inviter_name ?? "A manager"} invited <strong>{preview.email}</strong> to join{" "}
        <strong>{preview.project_name}</strong> ({preview.workspace_name}) as {preview.role}.
      </p>
      {error ? <Alert tone="error">{error}</Alert> : null}

      {preview.status !== "pending" ? (
        <Alert tone="error">
          This invitation has {preview.status === "accepted" ? "already been used" : preview.status === "revoked" ? "been withdrawn" : "expired"}.
          Ask for a new one.
        </Alert>
      ) : me ? (
        me.email === preview.email ? (
          <Button onClick={accept} pending={accepting}>
            Accept and open the project
          </Button>
        ) : (
          <Alert tone="info">
            You&apos;re signed in as {me.email}. Sign out and sign in as {preview.email} to accept.
          </Alert>
        )
      ) : (
        <div className="flex flex-col gap-2">
          <Link
            href={`/sign-in?next=${encodeURIComponent(here)}`}
            className="inline-flex justify-center rounded-sm bg-accent px-3.5 py-2 text-sm font-medium text-on-accent hover:bg-accent-strong"
          >
            Sign in to accept
          </Link>
          <Link
            href={`/sign-up?email=${encodeURIComponent(preview.email)}`}
            className="text-center text-sm text-link hover:underline"
          >
            New here? Create an account with {preview.email}
          </Link>
          <p className="text-xs text-muted">
            After confirming your email, open the invitation link again.
          </p>
        </div>
      )}
    </div>
  );
}
