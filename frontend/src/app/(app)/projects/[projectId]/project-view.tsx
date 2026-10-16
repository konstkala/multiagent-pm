"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Alert, Badge, Button, Card, Loading, Select, TextField } from "@/components/ui";
import { api, call, errorText, send, type Member, type Project } from "@/lib/api/client";
import { keys, useMe, useMembers, useProject, useTickets } from "@/lib/queries";

type Role = Member["role"];

export function ProjectView() {
  const { projectId } = useParams<{ projectId: string }>();
  const project = useProject(projectId);

  if (project.isPending) return <Loading />;
  if (project.isError) return <Alert tone="error">{errorText(project.error)}</Alert>;
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <Link href="/projects" className="text-sm text-accent hover:underline">
          ← All projects
        </Link>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">{project.data.name}</h1>
          <span className="font-mono text-sm text-muted">{project.data.key}</span>
          <Badge>{project.data.role}</Badge>
        </div>
        {project.data.description ? (
          <p className="max-w-2xl text-sm text-muted">{project.data.description}</p>
        ) : null}
      </div>
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <TicketsPanel project={project.data} />
        </div>
        <MembersPanel project={project.data} />
      </div>
    </div>
  );
}

function TicketsPanel({ project }: { project: Project }) {
  const tickets = useTickets(project.id);
  const queryClient = useQueryClient();
  const create = useMutation({
    mutationFn: (body: { title: string; description: string }) =>
      call(
        api.POST("/projects/{project_id}/tickets", {
          params: { path: { project_id: project.id } },
          body,
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.tickets(project.id) }),
  });

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    create.mutate(
      { title: String(form.get("title")), description: String(form.get("description")) },
      { onSuccess: () => formElement.reset() },
    );
  }

  return (
    <Card title={`Tickets${tickets.data ? ` (${tickets.data.total})` : ""}`}>
      <div className="flex flex-col gap-5">
        <form onSubmit={onSubmit} className="flex flex-col gap-3">
          {create.isError ? <Alert tone="error">{errorText(create.error)}</Alert> : null}
          <TextField label="New ticket" name="title" required maxLength={200} placeholder="What needs doing?" />
          <TextField label="Description" name="description" maxLength={20000} />
          <div>
            <Button type="submit" pending={create.isPending}>
              Create ticket
            </Button>
          </div>
        </form>
        {tickets.isPending ? <Loading /> : null}
        {tickets.isError ? <Alert tone="error">{errorText(tickets.error)}</Alert> : null}
        {tickets.data?.items.length === 0 ? (
          <p className="text-sm text-muted">No tickets yet.</p>
        ) : null}
        <ul className="divide-y divide-border">
          {tickets.data?.items.map((ticket) => (
            <li key={ticket.id} className="flex items-center gap-3 py-2.5">
              <span className="w-20 shrink-0 font-mono text-xs text-muted">
                {project.key}-{ticket.number}
              </span>
              <span className="min-w-0 flex-1 truncate text-sm">{ticket.title}</span>
              {ticket.priority ? <Badge>{ticket.priority}</Badge> : null}
              <Badge>{ticket.status.replace("_", " ")}</Badge>
            </li>
          ))}
        </ul>
      </div>
    </Card>
  );
}

function MembersPanel({ project }: { project: Project }) {
  const members = useMembers(project.id);
  const me = useMe();
  const isManager = project.role === "manager";

  return (
    <Card title="Team">
      <div className="flex flex-col gap-5">
        {members.isPending ? <Loading /> : null}
        {members.isError ? <Alert tone="error">{errorText(members.error)}</Alert> : null}
        <ul className="flex flex-col gap-3">
          {members.data?.map((member) => (
            <MemberRow
              key={member.user_id}
              projectId={project.id}
              member={member}
              canManage={isManager}
              isMe={member.user_id === me.data?.id}
            />
          ))}
        </ul>
        {isManager ? <AddMember projectId={project.id} /> : null}
      </div>
    </Card>
  );
}

function MemberRow({
  projectId,
  member,
  canManage,
  isMe,
}: {
  projectId: string;
  member: Member;
  canManage: boolean;
  isMe: boolean;
}) {
  const queryClient = useQueryClient();
  const [confirmRemove, setConfirmRemove] = useState(false);
  const path = { project_id: projectId, user_id: member.user_id };
  const refresh = () => queryClient.invalidateQueries({ queryKey: keys.members(projectId) });

  const changeRole = useMutation({
    mutationFn: (role: Role) =>
      send(api.PATCH("/projects/{project_id}/members/{user_id}", { params: { path }, body: { role } })),
    onSuccess: refresh,
  });
  const remove = useMutation({
    mutationFn: () => send(api.DELETE("/projects/{project_id}/members/{user_id}", { params: { path } })),
    onSuccess: refresh,
  });
  const error = changeRole.error ?? remove.error;

  return (
    <li className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">
            {member.display_name}
            {isMe ? <span className="text-muted"> (you)</span> : null}
          </p>
          <p className="truncate text-xs text-muted">{member.email}</p>
        </div>
        {canManage ? (
          <select
            aria-label={`Role of ${member.display_name}`}
            value={member.role}
            disabled={changeRole.isPending}
            onChange={(event) => changeRole.mutate(event.target.value === "manager" ? "manager" : "employee")}
            className="rounded-md border border-border bg-surface px-2 py-1 text-xs"
          >
            <option value="manager">manager</option>
            <option value="employee">employee</option>
          </select>
        ) : (
          <Badge>{member.role}</Badge>
        )}
      </div>
      {canManage && !isMe ? (
        <div>
          {confirmRemove ? (
            <div className="flex gap-2">
              <Button variant="danger" pending={remove.isPending} onClick={() => remove.mutate()}>
                Remove from project
              </Button>
              <Button variant="secondary" onClick={() => setConfirmRemove(false)}>
                Keep
              </Button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setConfirmRemove(true)}
              className="text-xs text-danger hover:underline"
            >
              Remove…
            </button>
          )}
        </div>
      ) : null}
      {error ? <Alert tone="error">{errorText(error)}</Alert> : null}
    </li>
  );
}

function AddMember({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const add = useMutation({
    mutationFn: (body: { email: string; role: Role }) =>
      call(
        api.POST("/projects/{project_id}/members", {
          params: { path: { project_id: projectId } },
          body,
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.members(projectId) }),
  });

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    add.mutate(
      {
        email: String(form.get("email")),
        role: form.get("role") === "manager" ? "manager" : "employee",
      },
      { onSuccess: () => formElement.reset() },
    );
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-3 border-t border-border pt-4">
      <p className="text-sm font-medium">Add someone</p>
      <p className="text-xs text-muted">They need an account with a confirmed email.</p>
      {add.isError ? <Alert tone="error">{errorText(add.error)}</Alert> : null}
      <TextField label="Email" name="email" type="email" required />
      <Select label="Role" name="role" defaultValue="employee">
        <option value="employee">employee</option>
        <option value="manager">manager</option>
      </Select>
      <Button type="submit" pending={add.isPending}>
        Add to project
      </Button>
    </form>
  );
}
