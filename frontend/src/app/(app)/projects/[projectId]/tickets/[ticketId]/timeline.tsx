"use client";

import type { ReactNode } from "react";

import { Alert, Loading } from "@/components/ui";
import { errorText, type Schemas } from "@/lib/api/client";
import {
  useAssignmentSuggestions,
  useComments,
  useSplit,
  useTicketEvents,
  useTriage,
} from "@/lib/queries";
import { STATUS_LABEL, formatTime, pick, STATUSES } from "@/lib/tickets";

import { AssignmentPanel } from "./assignment-panel";
import { CommentForm, CommentItem } from "./comments";
import { SplitPanel, canSplit } from "./split-panel";
import type { TicketContext } from "./ticket-detail";
import { TriagePanel } from "./triage-panel";

type TicketEvent = Schemas["TicketEventRead"];

type Entry = { at: string; key: string; node: ReactNode };

/**
 * The ticket's story in one list, oldest first: the description, then what people and agents
 * did, as it happened (like an issue on GitHub). The comment box closes it.
 */
export function Timeline({ context, intro }: { context: TicketContext; intro: ReactNode }) {
  const { ticket, isManager } = context;
  const comments = useComments(ticket.id);
  const events = useTicketEvents(ticket.id);
  const triage = useTriage(ticket.id);
  const assignment = useAssignmentSuggestions(ticket.id, isManager);
  const showSplit = canSplit(context);
  const split = useSplit(ticket.id, showSplit);

  const entries: Entry[] = [];
  for (const comment of comments.data ?? []) {
    entries.push({
      at: comment.created_at,
      key: `comment-${comment.id}`,
      node: <CommentItem comment={comment} context={context} />,
    });
  }
  for (const event of events.data ?? []) {
    if (event.kind === "created") continue; // the description card says who opened it
    entries.push({ at: event.created_at, key: `event-${event.id}`, node: <EventLine event={event} /> });
  }
  if (triage.data) {
    entries.push({ at: triage.data.created_at, key: "triage", node: <TriagePanel context={context} /> });
  } else if (isManager && triage.isSuccess) {
    // Not triaged yet: the panel offers "Triage now". It belongs at the end.
    entries.push({ at: "9999", key: "triage", node: <TriagePanel context={context} /> });
  }
  if (isManager) {
    entries.push({
      at: assignment.data?.created_at ?? "9999",
      key: "assignment",
      node: <AssignmentPanel context={context} />,
    });
  }
  if (showSplit) {
    entries.push({
      at: split.data?.created_at ?? "9999",
      key: "split",
      node: <SplitPanel context={context} />,
    });
  }
  entries.sort((a, b) => a.at.localeCompare(b.at));

  const loading = comments.isPending || events.isPending;
  const error = comments.error ?? events.error;

  return (
    <section aria-label="Activity" className="flex flex-col gap-4">
      {intro}
      {loading ? <Loading /> : null}
      {error ? <Alert tone="error">{errorText(error)}</Alert> : null}
      <ol className="flex flex-col gap-4">
        {entries.map((entry) => (
          <li key={entry.key}>{entry.node}</li>
        ))}
      </ol>
      <CommentForm context={context} />
    </section>
  );
}

function EventLine({ event }: { event: TicketEvent }) {
  const who = event.actor_name ?? "Someone";
  return (
    <p className="border-l-2 border-border pl-3 text-sm text-muted">
      <strong className="font-medium text-foreground">{who}</strong> {describe(event)} ·{" "}
      <time dateTime={event.created_at}>{formatTime(event.created_at)}</time>
    </p>
  );
}

function describe(event: TicketEvent): ReactNode {
  if (event.kind === "status") {
    const status = pick(STATUSES, event.to_value ?? "");
    return (
      <>
        moved this to <strong className="font-medium text-foreground">{status ? STATUS_LABEL[status] : event.to_value}</strong>
      </>
    );
  }
  if (event.to_value) {
    return (
      <>
        assigned this to <strong className="font-medium text-foreground">{event.to_value}</strong>
      </>
    );
  }
  return <>unassigned {event.from_value ?? "this ticket"}</>;
}
