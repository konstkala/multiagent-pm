"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { splitLabels } from "@/components/create-ticket";
import { Alert, Badge, Button, Card } from "@/components/ui";
import { api, call, errorText, type Schemas, type TriageRun } from "@/lib/api/client";
import { keys, useTriage } from "@/lib/queries";
import { CATEGORIES, PRIORITIES, STORY_POINTS, pick, ticketKey } from "@/lib/tickets";

import type { TicketContext } from "./ticket-detail";

type Proposal = Schemas["TriageProposalRead"];
type Changes = Schemas["TriageAccept"];

const STATUS_TEXT: Record<Schemas["TriageStatus"], string> = {
  queued: "Working",
  needs_answer: "Question",
  proposed: "Suggestion",
  applied: "Accepted",
  dismissed: "Dismissed",
  failed: "Failed",
};

// Short codes from the API; the API never sends exception text (it could echo ticket content).
const ERROR_TEXT: Record<string, string> = {
  refused: "The AI declined to triage this ticket.",
  over_budget: "Stopped at the $0.05 per-run budget.",
  ai_unavailable: "The AI service was unavailable.",
  storage_unavailable: "The attachments couldn't be read.",
  ticket_missing: "The ticket was deleted.",
};

/** The triage agent's latest run: progress, its one question, and a suggestion a manager decides on. */
export function TriagePanel({ context }: { context: TicketContext }) {
  const { ticket, isManager } = context;
  const triage = useTriage(ticket.id);
  const run = triage.data;
  useRefreshTicketWhenFinished(context, run?.status);

  if (triage.isPending) return null;
  if (triage.isError) {
    return (
      <Card title="AI triage">
        <Alert tone="error">{errorText(triage.error)}</Alert>
      </Card>
    );
  }
  if (!run) {
    return isManager ? (
      <Card title="AI triage">
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm text-muted">Not triaged yet.</p>
          <RerunButton context={context} label="Triage now" />
        </div>
      </Card>
    ) : null;
  }
  return (
    <Card title="AI triage" actions={<Badge>{STATUS_TEXT[run.status]}</Badge>}>
      <div className="flex flex-col gap-4">
        <RunBody run={run} context={context} />
        <RunCost run={run} />
      </div>
    </Card>
  );
}

function RunBody({ run, context }: { run: TriageRun; context: TicketContext }) {
  const { isManager } = context;
  switch (run.status) {
    case "queued":
      return (
        <p className="text-sm text-muted" aria-live="polite">
          {run.answer ? "The agent is reading your answer…" : "The agent is reading the ticket…"}
        </p>
      );
    case "needs_answer":
      return <Question run={run} context={context} />;
    case "proposed":
      if (!run.proposal) return null;
      return isManager ? (
        <ProposalForm key={run.id} run={run} proposal={run.proposal} context={context} />
      ) : (
        <ProposalView run={run} proposal={run.proposal} context={context} />
      );
    case "applied":
    case "dismissed":
      return (
        <div className="flex flex-col gap-3">
          {run.status === "applied" && run.proposal ? (
            <ProposalView run={run} proposal={run.proposal} context={context} />
          ) : (
            <p className="text-sm text-muted">The suggestion was dismissed.</p>
          )}
          {isManager ? <RerunButton context={context} label="Run again" /> : null}
        </div>
      );
    case "failed":
      return (
        <div className="flex flex-col gap-3">
          <Alert tone="error">{ERROR_TEXT[run.error_code ?? ""] ?? "Triage failed."}</Alert>
          {isManager ? <RerunButton context={context} label="Try again" /> : null}
        </div>
      );
  }
}

function Question({ run, context }: { run: TriageRun; context: TicketContext }) {
  const [text, setText] = useState("");
  const answer = useTriageAction(context, () =>
    call(
      api.POST("/triage-runs/{run_id}/answer", {
        params: { path: { run_id: run.id } },
        body: { answer: text.trim() },
      }),
    ),
  );

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm">
        <span className="text-muted">The agent asks: </span>
        {run.question}
      </p>
      {context.isManager ? (
        <>
          <textarea
            aria-label="Your answer"
            value={text}
            rows={3}
            maxLength={2000}
            onChange={(event) => setText(event.target.value)}
            className="rounded-md border border-border bg-surface px-3 py-2 text-sm outline-none focus:border-accent"
          />
          {answer.isError ? <Alert tone="error">{errorText(answer.error)}</Alert> : null}
          <div className="flex gap-2">
            <Button disabled={!text.trim()} pending={answer.isPending} onClick={() => answer.mutate()}>
              Send answer
            </Button>
            <DismissButton run={run} context={context} />
          </div>
        </>
      ) : (
        <p className="text-xs text-muted">Waiting for a manager to answer.</p>
      )}
    </div>
  );
}

/** Each field can be kept (and edited) or left out. A duplicate is opt-in: closing work is a bigger call. */
function ProposalForm({
  run,
  proposal,
  context,
}: {
  run: TriageRun;
  proposal: Proposal;
  context: TicketContext;
}) {
  const [keep, setKeep] = useState({
    category: true,
    labels: true,
    priority: true,
    story_points: true,
    duplicate_of: false,
  });
  const [category, setCategory] = useState(proposal.category);
  const [labels, setLabels] = useState(proposal.labels.join(", "));
  const [priority, setPriority] = useState(proposal.priority);
  // The backend already snaps points to the scale; the fallback only satisfies the type.
  const [points, setPoints] = useState(
    STORY_POINTS.find((p) => p === proposal.story_points) ?? STORY_POINTS[0],
  );
  const accept = useTriageAction(context, (changes: Changes) =>
    call(
      api.POST("/triage-runs/{run_id}/accept", {
        params: { path: { run_id: run.id } },
        body: changes,
      }),
    ),
  );

  function changes(): Changes {
    const kept: Changes = {};
    if (keep.category) kept.category = category;
    if (keep.labels) kept.labels = splitLabels(labels);
    if (keep.priority) kept.priority = priority;
    if (keep.story_points) kept.story_points = points;
    if (keep.duplicate_of && proposal.duplicate_of_id) kept.duplicate_of = proposal.duplicate_of_id;
    return kept;
  }

  const toggle = (field: keyof typeof keep) => (kept: boolean) =>
    setKeep((current) => ({ ...current, [field]: kept }));

  return (
    <div className="flex flex-col gap-4">
      <Reason run={run} proposal={proposal} />
      <div className="flex flex-col gap-2.5">
        <KeepRow label="Category" kept={keep.category} onKeep={toggle("category")}>
          <select
            aria-label="Suggested category"
            value={category}
            onChange={(event) => setCategory(pick(CATEGORIES, event.target.value) ?? category)}
            className={inputClass}
          >
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </KeepRow>
        <KeepRow label="Labels" kept={keep.labels} onKeep={toggle("labels")}>
          <input
            aria-label="Suggested labels"
            value={labels}
            onChange={(event) => setLabels(event.target.value)}
            className={inputClass}
          />
        </KeepRow>
        <KeepRow label="Priority" kept={keep.priority} onKeep={toggle("priority")}>
          <select
            aria-label="Suggested priority"
            value={priority}
            onChange={(event) => setPriority(pick(PRIORITIES, event.target.value) ?? priority)}
            className={inputClass}
          >
            {PRIORITIES.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </KeepRow>
        <KeepRow label="Story points" kept={keep.story_points} onKeep={toggle("story_points")}>
          <select
            aria-label="Suggested story points"
            value={points}
            onChange={(event) =>
              setPoints(STORY_POINTS.find((p) => String(p) === event.target.value) ?? points)
            }
            className={inputClass}
          >
            {STORY_POINTS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </KeepRow>
        {proposal.duplicate_of_id ? (
          <KeepRow label="Duplicate of" kept={keep.duplicate_of} onKeep={toggle("duplicate_of")}>
            <DuplicateLink proposal={proposal} context={context} />
          </KeepRow>
        ) : null}
      </div>
      {accept.isError ? <Alert tone="error">{errorText(accept.error)}</Alert> : null}
      <div className="flex gap-2">
        <Button pending={accept.isPending} onClick={() => accept.mutate(changes())}>
          Accept
        </Button>
        <DismissButton run={run} context={context} />
      </div>
    </div>
  );
}

function ProposalView({
  run,
  proposal,
  context,
}: {
  run: TriageRun;
  proposal: Proposal;
  context: TicketContext;
}) {
  return (
    <div className="flex flex-col gap-3">
      <Reason run={run} proposal={proposal} />
      <dl className="grid grid-cols-[8rem_1fr] gap-x-3 gap-y-1.5 text-sm">
        <dt className="text-muted">Category</dt>
        <dd className="capitalize">{proposal.category}</dd>
        <dt className="text-muted">Labels</dt>
        <dd>{proposal.labels.join(", ") || "None"}</dd>
        <dt className="text-muted">Priority</dt>
        <dd className="capitalize">{proposal.priority}</dd>
        <dt className="text-muted">Story points</dt>
        <dd>{proposal.story_points}</dd>
        {proposal.duplicate_of_id ? (
          <>
            <dt className="text-muted">Duplicate of</dt>
            <dd>
              <DuplicateLink proposal={proposal} context={context} />
            </dd>
          </>
        ) : null}
      </dl>
    </div>
  );
}

/** Why, how sure, and what the agent already changed on its own. */
function Reason({ run, proposal }: { run: TriageRun; proposal: Proposal }) {
  const percent = (value: number) => `${Math.round(value * 100)}%`;
  return (
    <div className="flex flex-col gap-1.5">
      <p className="text-sm">{proposal.reason}</p>
      <p className="text-xs text-muted">
        Sure of the type: {percent(proposal.classification_confidence)} · of the size:{" "}
        {percent(proposal.sizing_confidence)}
      </p>
      {run.auto_applied.length ? (
        <p className="text-xs text-muted">
          Already set by the agent: {run.auto_applied.join(" and ")}. Change them in the ticket
          fields if they&apos;re wrong.
        </p>
      ) : null}
    </div>
  );
}

function DuplicateLink({ proposal, context }: { proposal: Proposal; context: TicketContext }) {
  const { project } = context;
  if (!proposal.duplicate_of_id || proposal.duplicate_of === null) return null;
  return (
    <Link
      href={`/projects/${project.id}/tickets/${proposal.duplicate_of_id}`}
      className="text-sm hover:text-accent hover:underline"
    >
      <span className="font-mono text-xs text-muted">
        {ticketKey(project.key, proposal.duplicate_of)}
      </span>{" "}
      {proposal.duplicate_of_title}
    </Link>
  );
}

function KeepRow({
  label,
  kept,
  onKeep,
  children,
}: {
  label: string;
  kept: boolean;
  onKeep: (kept: boolean) => void;
  children: ReactNode;
}) {
  return (
    <div className="grid grid-cols-[8rem_1fr] items-center gap-3">
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={kept} onChange={(event) => onKeep(event.target.checked)} />
        {label}
      </label>
      <div className={kept ? "" : "opacity-50"}>{children}</div>
    </div>
  );
}

function RunCost({ run }: { run: TriageRun }) {
  if (!run.llm_calls) return null;
  const calls = run.llm_calls === 1 ? "1 call" : `${run.llm_calls} calls`;
  return (
    <p className="border-t border-border pt-3 text-xs text-muted">
      {run.model} · {calls} · ${run.cost_usd.toFixed(4)} · {(run.latency_ms / 1000).toFixed(1)} s
    </p>
  );
}

function DismissButton({ run, context }: { run: TriageRun; context: TicketContext }) {
  const dismiss = useTriageAction(context, () =>
    call(api.POST("/triage-runs/{run_id}/dismiss", { params: { path: { run_id: run.id } } })),
  );
  return (
    <Button variant="secondary" pending={dismiss.isPending} onClick={() => dismiss.mutate()}>
      Dismiss
    </Button>
  );
}

function RerunButton({ context, label }: { context: TicketContext; label: string }) {
  const { ticket } = context;
  const rerun = useTriageAction(context, () =>
    call(api.POST("/tickets/{ticket_id}/triage", { params: { path: { ticket_id: ticket.id } } })),
  );
  return (
    <div className="flex flex-col gap-2">
      <Button variant="secondary" pending={rerun.isPending} onClick={() => rerun.mutate()}>
        {label}
      </Button>
      {rerun.isError ? <Alert tone="error">{errorText(rerun.error)}</Alert> : null}
    </div>
  );
}

/** Any triage action returns the run: show it at once; an accept also changed the ticket. */
function useTriageAction<T = void>(context: TicketContext, action: (input: T) => Promise<TriageRun>) {
  const { ticket } = context;
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: action,
    onSuccess: async (run) => {
      queryClient.setQueryData(keys.triage(ticket.id), run);
      if (run.status === "applied") await refreshTicket(queryClient, ticket);
    },
  });
}

/** The agent may have set category and labels by itself, so reload the ticket when it finishes. */
function useRefreshTicketWhenFinished(context: TicketContext, status: TriageRun["status"] | undefined) {
  const { ticket } = context;
  const queryClient = useQueryClient();
  const previous = useRef(status);
  useEffect(() => {
    if (previous.current === "queued" && status !== "queued") void refreshTicket(queryClient, ticket);
    previous.current = status;
  }, [status, queryClient, ticket]);
}

async function refreshTicket(
  queryClient: ReturnType<typeof useQueryClient>,
  ticket: TicketContext["ticket"],
) {
  // exact: the ticket key is also the prefix of its comments, attachments and triage.
  await queryClient.invalidateQueries({ queryKey: keys.ticket(ticket.id), exact: true });
  await queryClient.invalidateQueries({ queryKey: keys.ticketLists(ticket.project_id) });
}

const inputClass =
  "w-full rounded-md border border-border bg-surface px-2 py-1.5 text-sm outline-none focus:border-accent";
