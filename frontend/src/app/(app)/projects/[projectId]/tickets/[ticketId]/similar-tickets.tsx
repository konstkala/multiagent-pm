"use client";

import Link from "next/link";

import { StatusPill } from "@/components/tickets";
import { Card } from "@/components/ui";
import { useSimilar } from "@/lib/queries";
import { ticketKey } from "@/lib/tickets";

import type { TicketContext } from "./ticket-detail";

/** Nearest tickets by meaning (local embeddings, no LLM cost): likely duplicates or prior work. */
export function SimilarTickets({ context }: { context: TicketContext }) {
  const { ticket, project } = context;
  const similar = useSimilar(ticket.id);

  return (
    <Card title="Similar tickets">
      {similar.isPending ? <p className="text-xs text-muted">Looking…</p> : null}
      {similar.isError ? (
        <p className="text-xs text-muted">Similarity isn&apos;t available for this ticket yet.</p>
      ) : null}
      {similar.data?.items.length === 0 ? (
        <p className="text-xs text-muted">Nothing similar in this project.</p>
      ) : null}
      <ul className="flex flex-col gap-2.5">
        {similar.data?.items.map(({ ticket: other, similarity }) => (
          <li key={other.id} className="flex flex-col gap-1">
            <Link
              href={`/projects/${project.id}/tickets/${other.id}`}
              className="line-clamp-2 text-sm hover:text-accent hover:underline"
            >
              <span className="font-mono text-xs text-muted">{ticketKey(project.key, other.number)}</span>{" "}
              {other.title}
            </Link>
            <span className="flex items-center gap-2">
              <StatusPill status={other.status} />
              <span className="text-xs text-muted" title="Cosine similarity of the two tickets">
                {Math.round(similarity * 100)}% match
              </span>
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}
