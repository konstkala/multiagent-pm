"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Avatar } from "@/components/tickets";
import { Alert, Badge, Button, Card, Loading, Select, TextField } from "@/components/ui";
import { api, call, errorText, send, type Member } from "@/lib/api/client";
import { keys, useMe, useMembers, useProject } from "@/lib/queries";

type Role = Member["role"];

export function TeamView() {
  const { projectId } = useParams<{ projectId: string }>();
  const project = useProject(projectId);
  const members = useMembers(projectId);
  const me = useMe();

  if (project.isPending || members.isPending) return <Loading />;
  if (project.isError) return <Alert tone="error">{errorText(project.error)}</Alert>;
  if (members.isError) return <Alert tone="error">{errorText(members.error)}</Alert>;
  const isManager = project.data.role === "manager";

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="lg:col-span-2">
        <Card title={`Team (${members.data.length})`}>
          <ul className="divide-y divide-border">
            {members.data.map((member) => (
              <MemberRow
                key={member.user_id}
                projectId={projectId}
                member={member}
                canManage={isManager}
                isMe={member.user_id === me.data?.id}
              />
            ))}
          </ul>
        </Card>
      </div>
      {isManager ? (
        <Card title="Add someone">
          <AddMember projectId={projectId} />
        </Card>
      ) : null}
    </div>
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
    <li className="flex flex-col gap-2 py-3">
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <Avatar name={member.display_name} />
          <div className="min-w-0">
            <p className="truncate text-sm font-medium">
              {member.display_name}
              {isMe ? <span className="text-muted"> (you)</span> : null}
            </p>
            <p className="truncate text-xs text-muted">{member.email}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {canManage ? (
            <select
              aria-label={`Role of ${member.display_name}`}
              value={member.role}
              disabled={changeRole.isPending}
              onChange={(event) =>
                changeRole.mutate(event.target.value === "manager" ? "manager" : "employee")
              }
              className="rounded-md border border-border bg-surface px-2 py-1 text-xs"
            >
              <option value="manager">manager</option>
              <option value="employee">employee</option>
            </select>
          ) : (
            <Badge>{member.role}</Badge>
          )}
          {canManage && !isMe && !confirmRemove ? (
            <button
              type="button"
              onClick={() => setConfirmRemove(true)}
              className="text-xs text-danger hover:underline"
            >
              Remove…
            </button>
          ) : null}
        </div>
      </div>
      {confirmRemove ? (
        <div className="flex gap-2">
          <Button variant="danger" pending={remove.isPending} onClick={() => remove.mutate()}>
            Remove {member.display_name} from the project
          </Button>
          <Button variant="secondary" onClick={() => setConfirmRemove(false)}>
            Keep
          </Button>
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
    <form onSubmit={onSubmit} className="flex flex-col gap-3">
      <p className="text-xs text-muted">They need an account with a confirmed email.</p>
      {add.isError ? <Alert tone="error">{errorText(add.error)}</Alert> : null}
      {add.isSuccess ? <Alert tone="success">Added.</Alert> : null}
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
