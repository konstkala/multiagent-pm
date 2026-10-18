"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState, type FormEvent } from "react";

import { CreateTicketForm } from "@/components/create-ticket";
import { AssigneeName, StatusPill } from "@/components/tickets";
import { Alert, Button, Card, Loading } from "@/components/ui";
import { ApiError, api, call, errorText, send, type Schemas } from "@/lib/api/client";
import { keys, useLinks, useTicket, useTickets } from "@/lib/queries";
import { ticketKey } from "@/lib/tickets";

import type { TicketContext } from "./ticket-detail";

type LinkType = Schemas["LinkType"];

const LINK_LABEL: Record<LinkType, { outgoing: string; incoming: string }> = {
  blocks: { outgoing: "Blocks", incoming: "Blocked by" },
  relates_to: { outgoing: "Relates to", incoming: "Relates to" },
};

export function Relations({ context }: { context: TicketContext }) {
  return (
    <div className="flex flex-col gap-6">
      {context.ticket.parent_id ? (
        <ParentTicket context={context} parentId={context.ticket.parent_id} />
      ) : (
        <SubTasks context={context} />
      )}
      <Links context={context} />
    </div>
  );
}

function ParentTicket({ context, parentId }: { context: TicketContext; parentId: string }) {
  const parent = useTicket(parentId);
  if (!parent.data) return null;
  return (
    <p className="text-sm text-muted">
      Sub-task of{" "}
      <Link
        href={`/projects/${context.project.id}/tickets/${parentId}`}
        className="font-medium text-link hover:underline"
      >
        {ticketKey(context.project.key, parent.data.number)} {parent.data.title}
      </Link>
    </p>
  );
}

function SubTasks({ context }: { context: TicketContext }) {
  const { ticket, project, members, isManager } = context;
  const subtasks = useTickets(project.id, { parent_id: ticket.id, limit: 100 });
  const [adding, setAdding] = useState(false);
  const items = subtasks.data?.items ?? [];
  const done = items.filter((t) => t.status === "done").length;

  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold">
          Sub-tasks{items.length ? ` (${done}/${items.length} done)` : ""}
        </h2>
        {isManager && !adding ? (
          <button type="button" onClick={() => setAdding(true)} className="text-xs font-medium text-link hover:underline">
            Add sub-task
          </button>
        ) : null}
      </div>
      {subtasks.isPending ? <Loading /> : null}
      {items.length ? (
        <ul className="divide-y divide-border rounded-sm border border-border bg-surface">
          {items.map((sub) => (
            <li key={sub.id} className="flex items-center gap-3 px-3 py-2">
              <span className="w-16 shrink-0 font-mono text-xs text-muted">
                {ticketKey(project.key, sub.number)}
              </span>
              <Link
                href={`/projects/${project.id}/tickets/${sub.id}`}
                className="min-w-0 flex-1 truncate text-sm hover:text-link hover:underline"
              >
                {sub.title}
              </Link>
              <span className="hidden max-w-32 sm:block">
                <AssigneeName assigneeId={sub.assignee_id} members={members} />
              </span>
              <StatusPill status={sub.status} />
            </li>
          ))}
        </ul>
      ) : !subtasks.isPending && !adding ? (
        <p className="text-sm text-muted">No sub-tasks.</p>
      ) : null}
      {adding ? (
        <Card title="New sub-task">
          <CreateTicketForm
            projectId={project.id}
            members={members}
            parentId={ticket.id}
            onCreated={() => setAdding(false)}
            onCancel={() => setAdding(false)}
          />
        </Card>
      ) : null}
    </section>
  );
}

function Links({ context }: { context: TicketContext }) {
  const { ticket, project, isManager } = context;
  const links = useLinks(ticket.id);
  const queryClient = useQueryClient();
  // A link shows on both tickets, so refresh every link list (and nothing else).
  const refresh = () =>
    queryClient.invalidateQueries({
      predicate: ({ queryKey }) => queryKey[0] === keys.links("")[0] && queryKey[2] === keys.links("")[2],
    });

  const remove = useMutation({
    mutationFn: (linkId: string) => send(api.DELETE("/links/{link_id}", { params: { path: { link_id: linkId } } })),
    onSuccess: refresh,
  });
  const add = useMutation({
    mutationFn: async ({ number, type }: { number: number; type: LinkType }) => {
      // People think in ticket keys (PM-12); the API wants ids, so look the number up first.
      const found = await call(
        api.GET("/projects/{project_id}/tickets", {
          params: { path: { project_id: project.id }, query: { q: String(number), limit: 20 } },
        }),
      );
      const target = found.items.find((t) => t.number === number);
      if (!target) throw new ApiError(404, "not_found", `${ticketKey(project.key, number)} doesn't exist`);
      return call(
        api.POST("/tickets/{ticket_id}/links", {
          params: { path: { ticket_id: ticket.id } },
          body: { target_id: target.id, type },
        }),
      );
    },
    onSuccess: refresh,
  });

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const number = Number(String(form.get("number")).replace(/^\D+/, ""));
    const type: LinkType = form.get("type") === "relates_to" ? "relates_to" : "blocks";
    if (Number.isInteger(number) && number > 0) {
      add.mutate({ number, type }, { onSuccess: () => formElement.reset() });
    }
  }

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-sm font-semibold">Links</h2>
      {links.data?.length ? (
        <ul className="flex flex-col gap-1.5">
          {links.data.map((link) => (
            <li key={link.id} className="flex items-center gap-3 text-sm">
              <span className="w-24 shrink-0 text-xs text-muted">{LINK_LABEL[link.type][link.direction]}</span>
              <Link
                href={`/projects/${project.id}/tickets/${link.ticket.id}`}
                className="min-w-0 flex-1 truncate hover:text-link hover:underline"
              >
                <span className="font-mono text-xs text-muted">{ticketKey(project.key, link.ticket.number)}</span>{" "}
                {link.ticket.title}
              </Link>
              <StatusPill status={link.ticket.status} />
              {isManager ? (
                <button
                  type="button"
                  onClick={() => remove.mutate(link.id)}
                  aria-label={`Remove link to ${ticketKey(project.key, link.ticket.number)}`}
                  className="text-xs text-muted hover:text-danger"
                >
                  Remove
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted">No links.</p>
      )}
      {isManager ? (
        <form onSubmit={onSubmit} className="flex flex-wrap items-end gap-2">
          <select
            name="type"
            aria-label="Link type"
            defaultValue="blocks"
            className="rounded-sm border border-border bg-surface px-2 py-1.5 text-sm"
          >
            <option value="blocks">Blocks</option>
            <option value="relates_to">Relates to</option>
          </select>
          <input
            name="number"
            aria-label="Ticket number"
            required
            placeholder={`${project.key}-12`}
            className="w-28 rounded-sm border border-border bg-surface px-2 py-1.5 text-sm"
          />
          <Button type="submit" variant="secondary" pending={add.isPending}>
            Link
          </Button>
        </form>
      ) : null}
      {add.isError || remove.isError ? <Alert tone="error">{errorText(add.error ?? remove.error)}</Alert> : null}
    </section>
  );
}
