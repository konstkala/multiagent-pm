"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { Alert, Badge, Button, Card } from "@/components/ui";
import { api, call, errorText, type Schemas } from "@/lib/api/client";
import { keys, useSplit } from "@/lib/queries";

import type { TicketContext } from "./ticket-detail";

type SplitRun = Schemas["SplitRunRead"];

/** Tickets below this are not worth splitting (the API enforces it too). */
export const MIN_SPLIT_POINTS = 8;

const STATUS_TEXT: Record<SplitRun["status"], string> = {
  queued: "Working",
  running: "Working",
  proposed: "Review",
  resuming: "Creating",
  applied: "Created",
  dismissed: "Rejected",
  failed: "Failed",
};

// Short codes from the API; the API never sends exception text (it could echo ticket content).
const ERROR_TEXT: Record<string, string> = {
  refused: "The AI declined to split this ticket.",
  over_budget: "Stopped at the $0.05 per-run budget.",
  rejected: "The AI service couldn't process this ticket.",
  ai_unavailable: "The AI service was unavailable.",
  ticket_missing: "The ticket was deleted.",
  ticket_changed: "The ticket changed while you were deciding. Start a new split.",
  decider_missing: "Your account was removed before the sub-tickets were created.",
};

/** Whether to show the panel at all: a big ticket, or one that already has a run to show. */
export function canSplit(context: TicketContext): boolean {
  const { ticket, isManager } = context;
  return isManager && !ticket.parent_id && (ticket.story_points ?? 0) >= MIN_SPLIT_POINTS;
}

/**
 * Managers only. A graph of agents drafts sub-tickets, a stronger model reviews the draft, and
 * nothing is created until a manager picks which pieces to keep.
 */
export function SplitPanel({ context }: { context: TicketContext }) {
  const { ticket } = context;
  const split = useSplit(ticket.id);
  const run = split.data;
  useRefreshTicketsWhenCreated(context, run?.status);

  if (split.isPending) return null;
  if (split.isError) {
    return (
      <Card tone="bot" title="Split into sub-tickets">
        <Alert tone="error">{errorText(split.error)}</Alert>
      </Card>
    );
  }
  if (!run) {
    return (
      <Card tone="bot" title="Split into sub-tickets">
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm text-muted">
            {ticket.story_points} points is a lot. An agent can propose smaller pieces.
          </p>
          <StartButton context={context} label="Split this ticket" />
        </div>
      </Card>
    );
  }
  return (
    <Card tone="bot" title="Split into sub-tickets" actions={<Badge>{STATUS_TEXT[run.status]}</Badge>}>
      <div className="flex flex-col gap-4">
        <RunBody run={run} context={context} />
        <RunCost run={run} />
      </div>
    </Card>
  );
}

function RunBody({ run, context }: { run: SplitRun; context: TicketContext }) {
  switch (run.status) {
    case "queued":
    case "running":
      return (
        <p className="text-sm text-muted" aria-live="polite">
          {progressText(run)}
        </p>
      );
    case "proposed":
      return <ProposalForm key={run.id} run={run} context={context} />;
    case "resuming":
      return (
        <p className="text-sm text-muted" aria-live="polite">
          Creating the sub-tickets…
        </p>
      );
    case "applied":
      return (
        <div className="flex flex-col gap-3">
          <p className="text-sm">
            Created {run.created_ticket_ids.length}{" "}
            {run.created_ticket_ids.length === 1 ? "sub-ticket" : "sub-tickets"}. They are listed
            under this ticket and each one is being triaged.
          </p>
        </div>
      );
    case "dismissed":
      return (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-muted">The proposal was rejected. Nothing was created.</p>
          <StartButton context={context} label="Split again" />
        </div>
      );
    case "failed":
      return (
        <div className="flex flex-col gap-3">
          <Alert tone="error">{ERROR_TEXT[run.error_code ?? ""] ?? "The split failed."}</Alert>
          <StartButton context={context} label="Try again" />
        </div>
      );
  }
}

/** What the graph is doing now, from the node that last finished. */
function progressText(run: SplitRun): string {
  switch (run.step) {
    case "draft":
      return "Draft written. A reviewer is checking it…";
    case "critique":
      return `Review ${run.rounds} done. Deciding whether to revise…`;
    case "revise":
      return "Draft revised. The reviewer is checking it again…";
    default:
      return run.status === "queued" ? "Waiting for the worker…" : "The agent is reading the ticket…";
  }
}

/** The graph's interrupt, as a screen: what would be created, with a checkbox for each piece. */
function ProposalForm({ run, context }: { run: SplitRun; context: TicketContext }) {
  const proposal = run.proposal;
  const [kept, setKept] = useState<number[]>(() => proposal?.sub_tickets.map((_, i) => i) ?? []);
  const decide = useDecide(context, run);
  if (!proposal) return null;

  function toggle(index: number, checked: boolean) {
    setKept((current) =>
      checked ? [...current, index].sort((a, b) => a - b) : current.filter((i) => i !== index),
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm">{proposal.reason}</p>
      <ol className="flex flex-col gap-3">
        {proposal.sub_tickets.map((sub, index) => (
          <li key={index} className="flex gap-2 border-b border-border pb-3 last:border-0 last:pb-0">
            <input
              id={`${run.id}-${index}`}
              type="checkbox"
              className="mt-1"
              checked={kept.includes(index)}
              onChange={(event) => toggle(index, event.target.checked)}
            />
            <label htmlFor={`${run.id}-${index}`} className="flex min-w-0 flex-col gap-1">
              <span className="flex items-baseline justify-between gap-2 text-sm font-medium">
                <span className="min-w-0 break-words">{sub.title}</span>
                <span className="shrink-0 text-xs font-normal text-muted">{sub.story_points} pts</span>
              </span>
              <span className="break-words text-sm text-muted">{sub.description}</span>
            </label>
          </li>
        ))}
      </ol>
      {proposal.issues.length ? (
        <Alert tone="info">
          The reviewer still had concerns after {proposal.rounds} rounds: {proposal.issues.join(" ")}
        </Alert>
      ) : null}
      <div className="flex items-center gap-2">
        <Button
          pending={decide.isPending}
          disabled={kept.length === 0}
          onClick={() => decide.mutate(kept)}
        >
          Create {kept.length} sub-{kept.length === 1 ? "ticket" : "tickets"}
        </Button>
        <Button variant="secondary" disabled={decide.isPending} onClick={() => decide.mutate([])}>
          Reject
        </Button>
      </div>
      {decide.isError ? <Alert tone="error">{errorText(decide.error)}</Alert> : null}
    </div>
  );
}

function StartButton({ context, label }: { context: TicketContext; label: string }) {
  const { ticket } = context;
  const queryClient = useQueryClient();
  const start = useMutation({
    mutationFn: () =>
      call(api.POST("/tickets/{ticket_id}/split", { params: { path: { ticket_id: ticket.id } } })),
    onSuccess: (run) => queryClient.setQueryData(keys.split(ticket.id), run),
  });
  return (
    <div className="flex flex-col gap-2">
      <Button variant="secondary" pending={start.isPending} onClick={() => start.mutate()}>
        {label}
      </Button>
      {start.isError ? <Alert tone="error">{errorText(start.error)}</Alert> : null}
    </div>
  );
}

function useDecide(context: TicketContext, run: SplitRun) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (keep: number[]) =>
      call(
        api.POST("/split-runs/{run_id}/decide", {
          params: { path: { run_id: run.id } },
          body: { keep },
        }),
      ),
    onSuccess: (updated) => queryClient.setQueryData(keys.split(context.ticket.id), updated),
  });
}

/** When the sub-tickets appear, refresh the lists they show up in (sub-tasks, board, counts). */
function useRefreshTicketsWhenCreated(context: TicketContext, status: SplitRun["status"] | undefined) {
  const { ticket } = context;
  const queryClient = useQueryClient();
  const previous = useRef(status);
  useEffect(() => {
    if (previous.current !== "applied" && status === "applied") {
      void queryClient.invalidateQueries({ queryKey: keys.ticketLists(ticket.project_id) });
      void queryClient.invalidateQueries({ queryKey: keys.events(ticket.id) });
    }
    previous.current = status;
  }, [status, ticket.id, ticket.project_id, queryClient]);
}

/** Where the money went: every LLM call of the graph, with its model. */
function RunCost({ run }: { run: SplitRun }) {
  if (!run.llm_calls) return null;
  const calls = run.llm_calls === 1 ? "1 call" : `${run.llm_calls} calls`;
  return (
    <details className="border-t border-border pt-3 text-xs text-muted">
      <summary className="cursor-pointer">
        {calls} · ${run.cost_usd.toFixed(4)} · {(run.latency_ms / 1000).toFixed(1)} s
      </summary>
      <ul className="mt-2 flex flex-col gap-1">
        {run.calls.map((call, index) => (
          <li key={index} className="font-mono">
            {call.node} · {call.model} · ${call.cost_usd.toFixed(4)} ·{" "}
            {(call.latency_ms / 1000).toFixed(1)} s
          </li>
        ))}
      </ul>
    </details>
  );
}
