"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent } from "react";

import { Alert, Button, Card, Loading, Select, TextField } from "@/components/ui";
import { api, call, errorText, send } from "@/lib/api/client";
import { peopleKeys, useInvitations } from "@/lib/queries";
import { formatTime } from "@/lib/tickets";

export function Invitations({ projectId }: { projectId: string }) {
  const pending = useInvitations(projectId, true);
  const queryClient = useQueryClient();
  const refresh = () => queryClient.invalidateQueries({ queryKey: peopleKeys.invitations(projectId) });

  const invite = useMutation({
    mutationFn: (body: { email: string; role: "manager" | "employee" }) =>
      call(
        api.POST("/projects/{project_id}/invitations", {
          params: { path: { project_id: projectId } },
          body,
        }),
      ),
    onSuccess: refresh,
  });
  const revoke = useMutation({
    mutationFn: (invitationId: string) =>
      send(api.DELETE("/invitations/{invitation_id}", { params: { path: { invitation_id: invitationId } } })),
    onSuccess: refresh,
  });

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    invite.mutate(
      {
        email: String(form.get("email")),
        role: form.get("role") === "manager" ? "manager" : "employee",
      },
      { onSuccess: () => formElement.reset() },
    );
  }

  return (
    <Card title="Invite people">
      <div className="flex flex-col gap-5">
        <form onSubmit={onSubmit} className="flex flex-col gap-3">
          <p className="text-xs text-muted">
            They get an email with a link. New people create an account with that address first.
          </p>
          {invite.isError ? <Alert tone="error">{errorText(invite.error)}</Alert> : null}
          {invite.isSuccess ? <Alert tone="success">Invitation sent.</Alert> : null}
          <TextField label="Email" name="email" type="email" required />
          <Select label="Role" name="role" defaultValue="employee">
            <option value="employee">employee</option>
            <option value="manager">manager</option>
          </Select>
          <Button type="submit" pending={invite.isPending}>
            Send invitation
          </Button>
        </form>

        <div className="flex flex-col gap-2 border-t border-border pt-4">
          <h3 className="text-sm font-medium">Waiting for an answer</h3>
          {pending.isPending ? <Loading /> : null}
          {pending.data?.length === 0 ? <p className="text-xs text-muted">None.</p> : null}
          {revoke.isError ? <Alert tone="error">{errorText(revoke.error)}</Alert> : null}
          <ul className="flex flex-col gap-2">
            {pending.data?.map((invitation) => (
              <li key={invitation.id} className="flex items-center justify-between gap-2 text-sm">
                <div className="min-w-0">
                  <p className="truncate">{invitation.email}</p>
                  <p className="text-xs text-muted">
                    {invitation.role} · expires {formatTime(invitation.expires_at)}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => revoke.mutate(invitation.id)}
                  className="shrink-0 text-xs text-muted hover:text-danger"
                >
                  Revoke
                </button>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </Card>
  );
}
