"use client";

import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState, type ReactNode } from "react";

import { Avatar, DueDate, Points, PriorityText } from "@/components/tickets";
import { Alert, Loading } from "@/components/ui";
import { api, call, errorText, type Member, type Schemas, type Ticket } from "@/lib/api/client";
import { keys, useMe, useMembers, useProject, useTickets, type TicketFilters } from "@/lib/queries";
import {
  OPEN_STATUSES,
  STATUSES,
  STATUS_LABEL,
  isClosed,
  pick,
  ticketKey,
  type Status,
} from "@/lib/tickets";

// One page of up to 200 tickets: plenty for a team board; filters and the list view cover more.
const BOARD_FILTERS: TicketFilters = { limit: 200 };

type TicketPage = Schemas["TicketPage"];

export function Board() {
  const { projectId } = useParams<{ projectId: string }>();
  const project = useProject(projectId);
  const members = useMembers(projectId);
  const me = useMe();
  const tickets = useTickets(projectId, BOARD_FILTERS);
  const queryClient = useQueryClient();
  const [notice, setNotice] = useState<string | null>(null);
  const listKey = keys.tickets(projectId, BOARD_FILTERS);

  // Small drag threshold, so a click on a card still opens it.
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor),
  );

  const move = useMutation({
    mutationFn: ({ ticketId, status }: { ticketId: string; status: Status }) =>
      call(api.PATCH("/tickets/{ticket_id}", { params: { path: { ticket_id: ticketId } }, body: { status } })),
    // Optimistic: the card moves now; if the API says no, it moves back.
    onMutate: async ({ ticketId, status }) => {
      await queryClient.cancelQueries({ queryKey: listKey });
      const previous = queryClient.getQueryData<TicketPage>(listKey);
      queryClient.setQueryData<TicketPage>(listKey, (page) =>
        page ? { ...page, items: page.items.map((t) => (t.id === ticketId ? { ...t, status } : t)) } : page,
      );
      return { previous };
    },
    onError: (error, _vars, context) => {
      if (context?.previous) queryClient.setQueryData(listKey, context.previous);
      setNotice(errorText(error));
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: keys.ticketLists(projectId) }),
  });

  if (project.isPending || members.isPending || me.isPending || tickets.isPending) return <Loading />;
  const error = project.error ?? members.error ?? me.error ?? tickets.error;
  if (error) return <Alert tone="error">{errorText(error)}</Alert>;
  if (!project.data || !me.data || !tickets.data) return <Loading />;

  const isManager = project.data.role === "manager";
  const myId = me.data.id;
  const canMove = (ticket: Ticket) =>
    isManager || (ticket.assignee_id === myId && !isClosed(ticket.status));
  const canDropInto = (status: Status) => isManager || OPEN_STATUSES.includes(status);

  function onDragEnd(event: DragEndEvent) {
    const status = pick(STATUSES, String(event.over?.id ?? ""));
    const ticket = tickets.data?.items.find((t) => t.id === String(event.active.id));
    if (!status || !ticket || status === ticket.status) return;
    if (!canDropInto(status)) {
      setNotice("Only managers can move tickets to Done or Cancelled.");
      return;
    }
    setNotice(null);
    move.mutate({ ticketId: ticket.id, status });
  }

  const byStatus = (status: Status) => tickets.data.items.filter((t) => t.status === status);

  return (
    <div className="flex flex-col gap-3">
      {!isManager ? (
        <p className="text-xs text-muted">
          You can drag your own tickets between To do, In progress and In review.
        </p>
      ) : null}
      {notice ? <Alert tone="error">{notice}</Alert> : null}
      {tickets.data.total > tickets.data.items.length ? (
        <Alert tone="info">
          Showing the newest {tickets.data.items.length} of {tickets.data.total} tickets. Use the list
          for the rest.
        </Alert>
      ) : null}
      <DndContext sensors={sensors} onDragEnd={onDragEnd}>
        <div className="grid auto-cols-[minmax(15rem,1fr)] grid-flow-col gap-3 overflow-x-auto pb-2">
          {STATUSES.map((status) => (
            <Column key={status} status={status} count={byStatus(status).length}>
              {byStatus(status).map((ticket) => (
                <Card
                  key={ticket.id}
                  ticket={ticket}
                  projectKey={project.data.key}
                  projectId={projectId}
                  members={members.data ?? []}
                  draggable={canMove(ticket)}
                />
              ))}
            </Column>
          ))}
        </div>
      </DndContext>
    </div>
  );
}

function Column({ status, count, children }: { status: Status; count: number; children: ReactNode }) {
  const { setNodeRef, isOver } = useDroppable({ id: status });
  return (
    <section
      ref={setNodeRef}
      aria-label={STATUS_LABEL[status]}
      className={`flex min-h-64 flex-col gap-2 rounded-sm border p-2 transition-colors ${
        isOver ? "border-accent bg-accent/5" : "border-border bg-subtle"
      }`}
    >
      <h2 className="flex items-center justify-between px-1 text-xs font-semibold uppercase tracking-wide text-muted">
        {STATUS_LABEL[status]}
        <span className="rounded-sm bg-surface px-2 py-0.5 font-medium">{count}</span>
      </h2>
      {children}
    </section>
  );
}

function Card({
  ticket,
  projectKey,
  projectId,
  members,
  draggable,
}: {
  ticket: Ticket;
  projectKey: string;
  projectId: string;
  members: Member[];
  draggable: boolean;
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: ticket.id,
    disabled: !draggable,
  });
  const assignee = members.find((m) => m.user_id === ticket.assignee_id);

  return (
    <article
      ref={setNodeRef}
      style={{ transform: CSS.Translate.toString(transform) }}
      className={`relative flex flex-col gap-2 rounded-sm border border-border bg-surface p-3 shadow-sm ${
        isDragging ? "z-10 opacity-80 shadow-lg" : ""
      }`}
    >
      {draggable ? (
        // The handle is the only draggable control (touch-none: a finger on it drags, a finger
        // on the card still scrolls). Keyboard: focus it, Space to lift, arrows to move.
        <button
          type="button"
          aria-label={`Move ${ticketKey(projectKey, ticket.number)}`}
          {...attributes}
          {...listeners}
          className="absolute right-1 top-1 cursor-grab touch-none rounded-sm px-1.5 py-0.5 text-muted hover:bg-subtle active:cursor-grabbing"
        >
          <span aria-hidden="true">⋮⋮</span>
        </button>
      ) : null}
      <Link
        href={`/projects/${projectId}/tickets/${ticket.id}`}
        className="line-clamp-3 pr-6 text-sm font-medium hover:text-link hover:underline"
      >
        {ticket.title}
      </Link>
      <div className="flex items-center gap-2">
        <span className="font-mono text-xs text-muted">{ticketKey(projectKey, ticket.number)}</span>
        <PriorityText priority={ticket.priority} />
        <span className="ml-auto flex items-center gap-1.5">
          <Points points={ticket.story_points} />
          {assignee ? <Avatar name={assignee.display_name} /> : null}
        </span>
      </div>
      {ticket.due_date ? <DueDate dueDate={ticket.due_date} status={ticket.status} /> : null}
    </article>
  );
}
