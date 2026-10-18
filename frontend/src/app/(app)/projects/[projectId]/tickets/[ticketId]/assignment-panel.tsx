"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Alert, Badge, Button, Card } from "@/components/ui";
import { api, call, errorText, type AssignmentRun, type Schemas } from "@/lib/api/client";
import { useUpdateTicket } from "@/lib/mutations";
import { keys, useAssignmentSuggestions } from "@/lib/queries";

import type { TicketContext } from "./ticket-detail";

type Candidate = Schemas["Candidate"];

/** Managers only. Code ranks the team (skills, past work, workload); the agent explains why. */
export function AssignmentPanel({ context }: { context: TicketContext }) {
  const { ticket } = context;
  const queryClient = useQueryClient();
  const suggestions = useAssignmentSuggestions(ticket.id);
  const suggest = useMutation({
    mutationFn: () =>
      call(
        api.POST("/tickets/{ticket_id}/assignment-suggestions", {
          params: { path: { ticket_id: ticket.id } },
        }),
      ),
    onSuccess: (run) => queryClient.setQueryData(keys.assignment(ticket.id), run),
  });
  const run = suggestions.data;

  const suggestButton = (label: string) => (
    <Button
      variant="secondary"
      pending={suggest.isPending}
      disabled={run?.status === "explaining"}
      onClick={() => suggest.mutate()}
    >
      {label}
    </Button>
  );

  return (
    <Card tone="bot" title="Suggested assignees">
      <div className="flex flex-col gap-3">
        {suggestions.isPending ? <p className="text-xs text-muted">Loading…</p> : null}
        {suggestions.isError ? <Alert tone="error">{errorText(suggestions.error)}</Alert> : null}
        {suggestions.isSuccess && !run ? (
          <>
            <p className="text-xs text-muted">
              Ranks the team by skills, similar work done and current workload.
            </p>
            {suggestButton("Suggest assignee")}
          </>
        ) : null}
        {run ? (
          <>
            {run.status === "explain_failed" ? (
              <Alert tone="info">The reasons couldn&apos;t be written; the ranking still stands.</Alert>
            ) : null}
            <ol className="flex flex-col gap-3">
              {run.candidates.map((candidate) => (
                <CandidateRow key={candidate.user_id} run={run} candidate={candidate} context={context} />
              ))}
            </ol>
            <RunCost run={run} />
            {suggestButton("Suggest again")}
          </>
        ) : null}
        {suggest.isError ? <Alert tone="error">{errorText(suggest.error)}</Alert> : null}
      </div>
    </Card>
  );
}

function CandidateRow({
  run,
  candidate,
  context,
}: {
  run: AssignmentRun;
  candidate: Candidate;
  context: TicketContext;
}) {
  const { ticket } = context;
  const update = useUpdateTicket(ticket);
  const assigned = ticket.assignee_id === candidate.user_id;

  return (
    <li className="flex flex-col gap-1.5 border-b border-border pb-3 last:border-0 last:pb-0">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium">
          {candidate.rank}. {candidate.display_name}
        </span>
        <span className="text-xs text-muted" title="Weighted score: skills 45%, similar work 35%, availability 20%">
          {Math.round(candidate.score * 100)}%
        </span>
      </div>
      <p className="text-xs text-muted">{factsText(candidate.facts)}</p>
      {candidate.reason ? (
        <p className="text-sm">{candidate.reason}</p>
      ) : run.status === "explaining" ? (
        <p className="text-xs text-muted" aria-live="polite">
          Writing the reason…
        </p>
      ) : null}
      <div className="flex items-center gap-2">
        {assigned ? (
          <Badge>Assigned</Badge>
        ) : (
          <Button
            variant="secondary"
            pending={update.isPending}
            onClick={() => update.mutate({ assignee_id: candidate.user_id })}
          >
            Assign
          </Button>
        )}
      </div>
      {update.isError ? <Alert tone="error">{errorText(update.error)}</Alert> : null}
    </li>
  );
}

function factsText(facts: Candidate["facts"]): string {
  const parts: string[] = [];
  if (!facts.has_profile) parts.push("no profile yet");
  else if (facts.matched_skills.length) {
    parts.push(facts.matched_skills.map((s) => `${s.name} ${s.level}/5`).join(", "));
  } else parts.push("no matching skill");
  if (facts.similar_done) parts.push(`${facts.similar_done} similar done`);
  parts.push(`${facts.open_points} open pts (avg ${facts.team_avg_points})`);
  if (facts.overdue) parts.push(`${facts.overdue} overdue`);
  return parts.join(" · ");
}

function RunCost({ run }: { run: AssignmentRun }) {
  const ranked = `Ranked in ${Math.round(run.score_ms)} ms`;
  const reasons = run.llm_calls
    ? ` · reasons: ${run.model} · $${run.cost_usd.toFixed(4)} · ${(run.latency_ms / 1000).toFixed(1)} s`
    : "";
  return <p className="border-t border-border pt-3 text-xs text-muted">{ranked + reasons}</p>;
}
