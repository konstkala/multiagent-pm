"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";

import { splitLabels } from "@/components/create-ticket";
import { AssigneeName, StatusPill } from "@/components/tickets";
import { Alert, Button, Card } from "@/components/ui";
import { api, call, errorText } from "@/lib/api/client";
import { useUpdateTicket } from "@/lib/mutations";
import { keys } from "@/lib/queries";
import {
  CATEGORIES,
  OPEN_STATUSES,
  PRIORITIES,
  STATUSES,
  STATUS_LABEL,
  STORY_POINTS,
  formatTime,
  isClosed,
  pick,
} from "@/lib/tickets";

import type { TicketContext } from "./ticket-detail";

export function Sidebar({ context }: { context: TicketContext }) {
  const { ticket, members, me, isManager } = context;
  const update = useUpdateTicket(ticket);
  const isAssignee = ticket.assignee_id === me.id;
  // Mirrors the API: managers move anything; assignees move their own open tickets.
  const statusOptions = isManager
    ? STATUSES
    : isAssignee && !isClosed(ticket.status)
      ? OPEN_STATUSES
      : [];
  const reporter = members.find((m) => m.user_id === ticket.reporter_id)?.display_name;

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <dl className="flex flex-col gap-4 text-sm">
          <Field label="Status" htmlFor="field-status">
            {statusOptions.length ? (
              <select
                id="field-status"
                value={ticket.status}
                disabled={update.isPending}
                onChange={(event) => {
                  const status = pick(STATUSES, event.target.value);
                  if (status) update.mutate({ status });
                }}
                className={selectClass}
              >
                {statusOptions.map((status) => (
                  <option key={status} value={status}>
                    {STATUS_LABEL[status]}
                  </option>
                ))}
              </select>
            ) : (
              <StatusPill status={ticket.status} />
            )}
          </Field>

          <Field label="Assignee" htmlFor="field-assignee">
            {isManager ? (
              <select
                id="field-assignee"
                value={ticket.assignee_id ?? ""}
                disabled={update.isPending}
                onChange={(event) => update.mutate({ assignee_id: event.target.value || null })}
                className={selectClass}
              >
                <option value="">Unassigned</option>
                {members.map((m) => (
                  <option key={m.user_id} value={m.user_id}>
                    {m.display_name}
                  </option>
                ))}
              </select>
            ) : (
              <AssigneeName assigneeId={ticket.assignee_id} members={members} />
            )}
          </Field>

          <Field label="Category" htmlFor="field-category">
            {isManager ? (
              <select
                id="field-category"
                value={ticket.category ?? ""}
                disabled={update.isPending}
                onChange={(event) => update.mutate({ category: pick(CATEGORIES, event.target.value) })}
                className={selectClass}
              >
                <option value="">Not set</option>
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            ) : (
              <span className="capitalize">{ticket.category ?? "Not set"}</span>
            )}
          </Field>

          <Field label="Priority" htmlFor="field-priority">
            {isManager ? (
              <select
                id="field-priority"
                value={ticket.priority ?? ""}
                disabled={update.isPending}
                onChange={(event) => update.mutate({ priority: pick(PRIORITIES, event.target.value) })}
                className={selectClass}
              >
                <option value="">Not set</option>
                {PRIORITIES.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            ) : (
              <span className="capitalize">{ticket.priority ?? "Not set"}</span>
            )}
          </Field>

          <Field label="Story points" htmlFor="field-points">
            {isManager ? (
              <select
                id="field-points"
                value={ticket.story_points ?? ""}
                disabled={update.isPending}
                onChange={(event) =>
                  update.mutate({
                    story_points: STORY_POINTS.find((p) => String(p) === event.target.value) ?? null,
                  })
                }
                className={selectClass}
              >
                <option value="">Not set</option>
                {STORY_POINTS.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            ) : (
              <span>{ticket.story_points ?? "Not set"}</span>
            )}
          </Field>

          <Field label="Due date" htmlFor="field-due">
            {isManager ? (
              <input
                id="field-due"
                type="date"
                value={ticket.due_date ?? ""}
                disabled={update.isPending}
                onChange={(event) => update.mutate({ due_date: event.target.value || null })}
                className={selectClass}
              />
            ) : (
              <span>{ticket.due_date ?? "Not set"}</span>
            )}
          </Field>

          <Field label="Labels" htmlFor="field-labels">
            {isManager ? (
              <input
                id="field-labels"
                key={ticket.labels.join(",")} // reset the box when the saved labels change
                defaultValue={ticket.labels.join(", ")}
                placeholder="backend, database"
                onBlur={(event) => {
                  const labels = splitLabels(event.target.value);
                  if (labels.join(",") !== ticket.labels.join(",")) update.mutate({ labels });
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter") event.currentTarget.blur();
                }}
                className={selectClass}
              />
            ) : ticket.labels.length ? (
              <span>{ticket.labels.join(", ")}</span>
            ) : (
              <span className="text-muted">None</span>
            )}
          </Field>

          <div className="flex flex-col gap-1 border-t border-border pt-3 text-xs text-muted">
            <span>Reported by {reporter ?? "a former member"}</span>
            <span>Created {formatTime(ticket.created_at)}</span>
            <span>Updated {formatTime(ticket.updated_at)}</span>
          </div>
        </dl>
        {update.isError ? (
          <div className="mt-3">
            <Alert tone="error">{errorText(update.error)}</Alert>
          </div>
        ) : null}
      </Card>

      {isManager ? <CopyTicket context={context} /> : null}
      {isAssignee && !isClosed(ticket.status) ? <ReturnTicket context={context} /> : null}
    </div>
  );
}

const selectClass =
  "w-full rounded-sm border border-border bg-surface px-2 py-1.5 text-sm outline-none focus:border-ring disabled:opacity-60";

function Field({ label, htmlFor, children }: { label: string; htmlFor: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <dt>
        <label htmlFor={htmlFor} className="text-xs font-medium text-muted">
          {label}
        </label>
      </dt>
      <dd>{children}</dd>
    </div>
  );
}

function CopyTicket({ context }: { context: TicketContext }) {
  const { ticket, project } = context;
  const router = useRouter();
  const queryClient = useQueryClient();
  const copy = useMutation({
    mutationFn: () =>
      call(api.POST("/tickets/{ticket_id}/copy", { params: { path: { ticket_id: ticket.id } } })),
    onSuccess: async (created) => {
      await queryClient.invalidateQueries({ queryKey: keys.ticketLists(project.id) });
      router.push(`/projects/${project.id}/tickets/${created.id}`);
    },
  });
  return (
    <div className="flex flex-col gap-2">
      <Button variant="secondary" pending={copy.isPending} onClick={() => copy.mutate()}>
        Copy as a new ticket
      </Button>
      {copy.isError ? <Alert tone="error">{errorText(copy.error)}</Alert> : null}
    </div>
  );
}

function ReturnTicket({ context }: { context: TicketContext }) {
  const { ticket } = context;
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const giveBack = useMutation({
    mutationFn: () =>
      call(
        api.POST("/tickets/{ticket_id}/return", {
          params: { path: { ticket_id: ticket.id } },
          body: { reason },
        }),
      ),
    onSuccess: async (updated) => {
      queryClient.setQueryData(keys.ticket(ticket.id), updated);
      await queryClient.invalidateQueries({ queryKey: keys.ticketLists(ticket.project_id) });
      await queryClient.invalidateQueries({ queryKey: keys.comments(ticket.id) });
      setOpen(false);
    },
  });

  if (!open) {
    return (
      <Button variant="secondary" onClick={() => setOpen(true)}>
        Return to manager…
      </Button>
    );
  }
  return (
    <Card title="Return to manager">
      <div className="flex flex-col gap-3">
        <label htmlFor="return-reason" className="text-xs text-muted">
          Why? The reason is posted as a comment.
        </label>
        <textarea
          id="return-reason"
          value={reason}
          rows={3}
          maxLength={2000}
          onChange={(event) => setReason(event.target.value)}
          className="rounded-sm border border-control bg-surface px-3 py-2 text-sm outline-none focus:border-ring"
        />
        {giveBack.isError ? <Alert tone="error">{errorText(giveBack.error)}</Alert> : null}
        <div className="flex gap-2">
          <Button
            disabled={reason.trim().length < 3}
            pending={giveBack.isPending}
            onClick={() => giveBack.mutate()}
          >
            Return ticket
          </Button>
          <Button variant="secondary" onClick={() => setOpen(false)}>
            Cancel
          </Button>
        </div>
      </div>
    </Card>
  );
}
