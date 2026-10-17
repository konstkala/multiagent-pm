"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useRef, useState, type ChangeEvent } from "react";

import { LEVEL_LABEL, ProfileForm, type ProfileValues } from "@/components/profile-form";
import { Alert, Button, Card, Loading } from "@/components/ui";
import { api, call, errorText, type CvImport, type Profile } from "@/lib/api/client";
import { peopleKeys, useCvImports, useMe, usePeople, useProfile } from "@/lib/queries";
import { formatBytes, formatTime } from "@/lib/tickets";

const CV_MAX_BYTES = 5 * 1024 * 1024; // the API enforces the same limit

const FAILURE: Record<string, string> = {
  refused: "The AI declined to read this document.",
  ai_unavailable: "The AI service wasn't available after three tries.",
  storage_unavailable: "File storage wasn't available. Upload the CV again.",
  over_budget: "This run reached its cost limit.",
  cv_missing: "The CV file was missing. Upload it again.",
};

export function ProfileView() {
  const { workspaceId, userId } = useParams<{ workspaceId: string; userId: string }>();
  const profile = useProfile(workspaceId, userId);
  const people = usePeople(workspaceId); // succeeds only for people managers
  const me = useMe();
  const [editing, setEditing] = useState(false);

  if (profile.isPending || people.isPending) return <Loading />;
  if (profile.isError) return <Alert tone="error">{errorText(profile.error)}</Alert>;
  const isManager = people.isSuccess;
  const isMe = me.data?.id === userId;

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      {isManager ? (
        <Link href={`/people/${workspaceId}`} className="text-sm text-accent hover:underline">
          ← People
        </Link>
      ) : null}
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          {profile.data.display_name}
          {isMe ? <span className="text-base font-normal text-muted"> (you)</span> : null}
        </h1>
        <p className="text-sm text-muted">{profile.data.email}</p>
      </div>

      {isManager ? <CvImports workspaceId={workspaceId} userId={userId} /> : null}

      {editing ? (
        <EditProfile profile={profile.data} workspaceId={workspaceId} onDone={() => setEditing(false)} />
      ) : (
        <Card
          title="Profile"
          actions={
            isManager ? (
              <Button variant="secondary" onClick={() => setEditing(true)}>
                Edit
              </Button>
            ) : null
          }
        >
          <ProfileSummary profile={profile.data} />
        </Card>
      )}
    </div>
  );
}

function ProfileSummary({ profile }: { profile: Profile }) {
  if (!profile.updated_at) {
    return <p className="text-sm text-muted">No profile yet. A manager can import a CV or fill it in.</p>;
  }
  return (
    <div className="flex flex-col gap-3 text-sm">
      {profile.headline ? <p className="font-medium">{profile.headline}</p> : null}
      {profile.years_experience !== null ? (
        <p className="text-muted">{profile.years_experience} years of experience</p>
      ) : null}
      {profile.summary ? <p className="whitespace-pre-wrap">{profile.summary}</p> : null}
      <ul className="flex flex-wrap gap-2">
        {profile.skills.map((skill) => (
          <li
            key={skill.name}
            title={LEVEL_LABEL[skill.level]}
            className="rounded-full border border-border bg-background px-2.5 py-1 text-xs"
          >
            {skill.name} <span className="text-muted">· {skill.level}/5</span>
          </li>
        ))}
      </ul>
      <p className="text-xs text-muted">Updated {formatTime(profile.updated_at)}</p>
    </div>
  );
}

function EditProfile({
  profile,
  workspaceId,
  onDone,
}: {
  profile: Profile;
  workspaceId: string;
  onDone: () => void;
}) {
  const queryClient = useQueryClient();
  const save = useMutation({
    mutationFn: (values: ProfileValues) =>
      call(
        api.PUT("/workspaces/{workspace_id}/people/{user_id}/profile", {
          params: { path: { workspace_id: workspaceId, user_id: profile.user_id } },
          body: values,
        }),
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: peopleKeys.people(workspaceId) });
      onDone();
    },
  });
  return (
    <Card title="Edit profile">
      {save.isError ? (
        <div className="mb-3">
          <Alert tone="error">{errorText(save.error)}</Alert>
        </div>
      ) : null}
      <ProfileForm
        initial={profile}
        submitLabel="Save profile"
        pending={save.isPending}
        onSubmit={(values) => save.mutate(values)}
        secondary={
          <Button type="button" variant="secondary" onClick={onDone}>
            Cancel
          </Button>
        }
      />
    </Card>
  );
}

function CvImports({ workspaceId, userId }: { workspaceId: string; userId: string }) {
  const imports = useCvImports(workspaceId, true);
  const queryClient = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const latest = imports.data?.find((cvImport) => cvImport.user_id === userId);

  const upload = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return call(
        api.POST("/workspaces/{workspace_id}/people/{user_id}/cv", {
          params: { path: { workspace_id: workspaceId, user_id: userId } },
          body: { file: file.name },
          bodySerializer: () => form,
        }),
      );
    },
    onSettled: async () => {
      if (input.current) input.current.value = "";
      await queryClient.invalidateQueries({ queryKey: peopleKeys.imports(workspaceId) });
    },
  });

  function onPick(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (file.size > CV_MAX_BYTES) {
      setLocalError(`${file.name} is ${formatBytes(file.size)}; CVs can be at most 5 MB.`);
      return;
    }
    setLocalError(null);
    upload.mutate(file);
  }

  return (
    <Card title="Import from a CV">
      <div className="flex flex-col gap-3">
        <p className="text-xs text-muted">
          An AI reads the PDF and drafts the profile. You review it before anything is saved. The CV
          is deleted as soon as it has been read.
        </p>
        <label className="w-fit cursor-pointer rounded-md border border-border px-3.5 py-2 text-sm font-medium hover:bg-background">
          {upload.isPending ? "Uploading…" : "Choose a PDF"}
          <input
            ref={input}
            type="file"
            accept="application/pdf,.pdf"
            onChange={onPick}
            disabled={upload.isPending}
            className="sr-only"
          />
        </label>
        {localError ? <Alert tone="error">{localError}</Alert> : null}
        {upload.isError ? <Alert tone="error">{errorText(upload.error)}</Alert> : null}
        {latest ? <ImportStatus cvImport={latest} workspaceId={workspaceId} /> : null}
      </div>
    </Card>
  );
}

function ImportStatus({ cvImport, workspaceId }: { cvImport: CvImport; workspaceId: string }) {
  if (cvImport.status === "queued") {
    return <Alert tone="info">Reading the CV… this usually takes under 10 seconds.</Alert>;
  }
  if (cvImport.status === "failed") {
    return <Alert tone="error">{FAILURE[cvImport.error_code ?? ""] ?? "The import failed."}</Alert>;
  }
  if (cvImport.status === "needs_review" && cvImport.draft) {
    return <ReviewDraft cvImport={cvImport} workspaceId={workspaceId} />;
  }
  return (
    <p className="text-xs text-muted">
      Last import {cvImport.status} · {formatTime(cvImport.created_at)}
    </p>
  );
}

function ReviewDraft({ cvImport, workspaceId }: { cvImport: CvImport; workspaceId: string }) {
  const queryClient = useQueryClient();
  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: peopleKeys.imports(workspaceId) });
    await queryClient.invalidateQueries({
      queryKey: peopleKeys.profile(workspaceId, cvImport.user_id),
    });
  };
  const path = { import_id: cvImport.id };
  const approve = useMutation({
    mutationFn: (values: ProfileValues) =>
      call(api.POST("/cv-imports/{import_id}/approve", { params: { path }, body: values })),
    onSuccess: refresh,
  });
  const reject = useMutation({
    mutationFn: () => call(api.POST("/cv-imports/{import_id}/reject", { params: { path } })),
    onSuccess: refresh,
  });
  const draft = cvImport.draft;
  if (!draft) return null;

  return (
    <div className="flex flex-col gap-3 border-t border-border pt-3">
      <div>
        <h3 className="text-sm font-semibold">Review the draft</h3>
        <p className="text-xs text-muted">
          Drafted by {cvImport.model ?? "the AI"}
          {cvImport.cost_usd !== null ? ` · $${cvImport.cost_usd.toFixed(4)}` : ""}
          {cvImport.latency_ms !== null ? ` · ${(cvImport.latency_ms / 1000).toFixed(1)} s` : ""}.
          Check every skill against its evidence; change anything before approving.
        </p>
      </div>
      {approve.isError || reject.isError ? (
        <Alert tone="error">{errorText(approve.error ?? reject.error)}</Alert>
      ) : null}
      <ProfileForm
        initial={draft}
        submitLabel="Approve and save"
        pending={approve.isPending}
        onSubmit={(values) => approve.mutate(values)}
        secondary={
          <Button type="button" variant="danger" pending={reject.isPending} onClick={() => reject.mutate()}>
            Reject draft
          </Button>
        }
      />
    </div>
  );
}
