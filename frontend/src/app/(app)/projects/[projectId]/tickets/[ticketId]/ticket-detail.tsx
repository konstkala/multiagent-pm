"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { StatusPill } from "@/components/tickets";
import { Alert, Button, Loading } from "@/components/ui";
import { errorText, type Member, type Project, type Ticket, type User } from "@/lib/api/client";
import { useUpdateTicket } from "@/lib/mutations";
import { useMe, useMembers, useProject, useTicket } from "@/lib/queries";
import { ticketKey } from "@/lib/tickets";

import { AssignmentPanel } from "./assignment-panel";
import { Attachments } from "./attachments";
import { Comments } from "./comments";
import { Relations } from "./relations";
import { Sidebar } from "./sidebar";
import { SimilarTickets } from "./similar-tickets";
import { TriagePanel } from "./triage-panel";

export type TicketContext = {
  ticket: Ticket;
  project: Project;
  members: Member[];
  me: User;
  isManager: boolean;
};

export function TicketDetail() {
  const { projectId, ticketId } = useParams<{ projectId: string; ticketId: string }>();
  const ticket = useTicket(ticketId);
  const project = useProject(projectId);
  const members = useMembers(projectId);
  const me = useMe();

  if (ticket.isPending || project.isPending || members.isPending || me.isPending) {
    return <Loading />;
  }
  const error = ticket.error ?? project.error ?? members.error ?? me.error;
  if (error) return <Alert tone="error">{errorText(error)}</Alert>;
  if (!ticket.data || !project.data || !members.data || !me.data) return <Loading />;

  const context: TicketContext = {
    ticket: ticket.data,
    project: project.data,
    members: members.data,
    me: me.data,
    isManager: project.data.role === "manager",
  };

  return (
    <div className="flex flex-col gap-4">
      <Link href={`/projects/${projectId}`} className="text-sm text-accent hover:underline">
        ← Tickets
      </Link>
      <div className="grid gap-6 lg:grid-cols-[1fr_18rem]">
        <div className="flex min-w-0 flex-col gap-6">
          <Header context={context} />
          <TriagePanel context={context} />
          <Description context={context} />
          <Relations context={context} />
          <Attachments context={context} />
          <Comments context={context} />
        </div>
        <div className="flex flex-col gap-6">
          <Sidebar context={context} />
          {context.isManager ? <AssignmentPanel context={context} /> : null}
          <SimilarTickets context={context} />
        </div>
      </div>
    </div>
  );
}

function Header({ context }: { context: TicketContext }) {
  const { ticket, project, isManager } = context;
  const update = useUpdateTicket(ticket);
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(ticket.title);

  function save() {
    const trimmed = title.trim();
    if (!trimmed || trimmed === ticket.title) {
      setEditing(false);
      return;
    }
    update.mutate({ title: trimmed }, { onSuccess: () => setEditing(false) });
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-3">
        <span className="font-mono text-sm text-muted">{ticketKey(project.key, ticket.number)}</span>
        <StatusPill status={ticket.status} />
      </div>
      {editing ? (
        <div className="flex flex-col gap-2">
          <input
            aria-label="Title"
            value={title}
            maxLength={200}
            onChange={(event) => setTitle(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") save();
              if (event.key === "Escape") setEditing(false);
            }}
            className="rounded-md border border-border bg-surface px-3 py-2 text-xl font-semibold outline-none focus:border-accent"
          />
          <div className="flex gap-2">
            <Button onClick={save} pending={update.isPending}>
              Save
            </Button>
            <Button variant="secondary" onClick={() => setEditing(false)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <h1 className="flex items-start gap-2 text-2xl font-semibold tracking-tight">
          <span className="min-w-0 break-words">{ticket.title}</span>
          {isManager ? (
            <button
              type="button"
              onClick={() => {
                setTitle(ticket.title);
                setEditing(true);
              }}
              className="mt-1.5 shrink-0 text-xs font-normal text-accent hover:underline"
            >
              Edit
            </button>
          ) : null}
        </h1>
      )}
      {update.isError ? <Alert tone="error">{errorText(update.error)}</Alert> : null}
    </div>
  );
}

function Description({ context }: { context: TicketContext }) {
  const { ticket, isManager } = context;
  const update = useUpdateTicket(ticket);
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(ticket.description);

  return (
    <section className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold">Description</h2>
        {isManager && !editing ? (
          <button
            type="button"
            onClick={() => {
              setText(ticket.description);
              setEditing(true);
            }}
            className="text-xs text-accent hover:underline"
          >
            Edit
          </button>
        ) : null}
      </div>
      {editing ? (
        <div className="flex flex-col gap-2">
          <textarea
            aria-label="Description"
            value={text}
            rows={8}
            maxLength={20000}
            onChange={(event) => setText(event.target.value)}
            className="rounded-md border border-border bg-surface px-3 py-2 text-sm outline-none focus:border-accent"
          />
          <div className="flex gap-2">
            <Button
              pending={update.isPending}
              onClick={() =>
                update.mutate({ description: text }, { onSuccess: () => setEditing(false) })
              }
            >
              Save
            </Button>
            <Button variant="secondary" onClick={() => setEditing(false)}>
              Cancel
            </Button>
          </div>
          {update.isError ? <Alert tone="error">{errorText(update.error)}</Alert> : null}
        </div>
      ) : ticket.description ? (
        // Plain text with line breaks kept: user text is never rendered as HTML.
        <p className="whitespace-pre-wrap break-words rounded-lg border border-border bg-surface p-4 text-sm leading-relaxed">
          {ticket.description}
        </p>
      ) : (
        <p className="text-sm text-muted">No description.</p>
      )}
    </section>
  );
}
