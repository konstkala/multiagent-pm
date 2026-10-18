"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState, type FormEvent } from "react";

import { Alert, Badge, Button, Card, Loading, TextField } from "@/components/ui";
import { api, call, errorText, type Workspace } from "@/lib/api/client";
import { keys, useMe, useProjects, useWorkspaces } from "@/lib/queries";

export function ProjectsView() {
  const workspaces = useWorkspaces();

  if (workspaces.isPending) return <Loading />;
  if (workspaces.isError) return <Alert tone="error">{errorText(workspaces.error)}</Alert>;
  return (
    <div className="flex flex-col gap-8">
      <h1 className="text-2xl font-semibold tracking-tight">Projects</h1>
      {workspaces.data.length === 0 ? (
        <CreateWorkspace />
      ) : (
        workspaces.data.map((workspace) => (
          <WorkspaceSection key={workspace.id} workspace={workspace} />
        ))
      )}
    </div>
  );
}

function WorkspaceSection({ workspace }: { workspace: Workspace }) {
  const projects = useProjects(workspace.id);
  const me = useMe();
  const [creating, setCreating] = useState(false);
  const isOwner = workspace.role === "owner";

  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold">{workspace.name}</h2>
          <Badge>{workspace.role}</Badge>
          <Link href={`/people/${workspace.id}`} className="text-sm text-link hover:underline">
            People
          </Link>
          {me.data ? (
            <Link
              href={`/people/${workspace.id}/${me.data.id}`}
              className="text-sm text-link hover:underline"
            >
              My profile
            </Link>
          ) : null}
        </div>
        {isOwner && !creating ? (
          <Button variant="secondary" onClick={() => setCreating(true)}>
            New project
          </Button>
        ) : null}
      </div>
      {creating ? (
        <CreateProject workspaceId={workspace.id} onDone={() => setCreating(false)} />
      ) : null}
      {projects.isPending ? <Loading /> : null}
      {projects.isError ? <Alert tone="error">{errorText(projects.error)}</Alert> : null}
      {projects.data?.length === 0 ? (
        <p className="text-sm text-muted">
          {isOwner ? "No projects yet. Create the first one." : "You aren't in any project here yet."}
        </p>
      ) : null}
      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {projects.data?.map((project) => (
          <li key={project.id}>
            <Link
              href={`/projects/${project.id}`}
              className="flex h-full flex-col gap-2 rounded-sm border border-border bg-surface p-4 hover:border-control"
            >
              <span className="font-mono text-xs text-muted">{project.key}</span>
              <span className="font-medium">{project.name}</span>
              <span className="mt-auto">
                <Badge>{project.role}</Badge>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

function CreateWorkspace() {
  const queryClient = useQueryClient();
  const create = useMutation({
    mutationFn: (name: string) => call(api.POST("/workspaces", { body: { name } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.workspaces }),
  });

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    create.mutate(String(new FormData(event.currentTarget).get("name")));
  }

  return (
    <Card title="Create your workspace">
      <form onSubmit={onSubmit} className="flex max-w-md flex-col gap-4">
        <p className="text-sm text-muted">
          A workspace is your company or team. You&apos;ll own it and can create projects in it.
        </p>
        {create.isError ? <Alert tone="error">{errorText(create.error)}</Alert> : null}
        <TextField label="Workspace name" name="name" required maxLength={100} placeholder="Acme" />
        <Button type="submit" pending={create.isPending}>
          Create workspace
        </Button>
      </form>
    </Card>
  );
}

function CreateProject({ workspaceId, onDone }: { workspaceId: string; onDone: () => void }) {
  const queryClient = useQueryClient();
  const create = useMutation({
    mutationFn: (body: { key: string; name: string; description: string }) =>
      call(
        api.POST("/workspaces/{workspace_id}/projects", {
          params: { path: { workspace_id: workspaceId } },
          body,
        }),
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: keys.projects(workspaceId) });
      onDone();
    },
  });

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    create.mutate({
      key: String(form.get("key")).toUpperCase(),
      name: String(form.get("name")),
      description: String(form.get("description")),
    });
  }

  return (
    <Card
      title="New project"
      actions={
        <Button variant="secondary" onClick={onDone}>
          Cancel
        </Button>
      }
    >
      <form onSubmit={onSubmit} className="grid gap-4 sm:grid-cols-[8rem_1fr]">
        {create.isError ? (
          <div className="sm:col-span-2">
            <Alert tone="error">{errorText(create.error)}</Alert>
          </div>
        ) : null}
        <TextField
          label="Key"
          name="key"
          required
          pattern="[A-Za-z][A-Za-z0-9]{1,9}"
          maxLength={10}
          placeholder="PM"
          hint="Ticket prefix: PM-1"
        />
        <TextField label="Name" name="name" required maxLength={100} placeholder="Platform" />
        <div className="sm:col-span-2">
          <TextField label="Description" name="description" maxLength={5000} />
        </div>
        <div className="sm:col-span-2">
          <Button type="submit" pending={create.isPending}>
            Create project
          </Button>
        </div>
      </form>
    </Card>
  );
}
