# Milestone 4: the triage agent

Parent: [product plan v1](2026-10-16-product-v1.md). Supersedes the LangGraph design in [phase 4 triage](2026-10-16-phase4-triage-workflow.md). UI stays functional until the user's UI session.

## Decisions (2026-10-17)
- **Orchestration**: job queue + run states in a `triage_runs` table, the pattern proven by the CV agent. LangGraph is deferred until an agent needs branching or tool loops (ADR 0016).
- **Auto-apply**: category and labels apply by themselves when the agent's confidence is ≥ 0.7 **and the field is still empty** (a person's choice is never overwritten). Priority, story points and duplicate always wait for a manager.
- **Trigger**: automatically when a ticket is created or copied; managers can re-run.
- **One clarifying question at most**: if the agent can't size the ticket, it asks the manager; the answer goes into a second run, which may not ask again.

## The agent
- Input (user turn, all treated as data): the ticket (key, title, description), up to 3 image attachments, up to 5 similar tickets in the project (≥ 0.6 similarity, with their category and points), labels the project already uses, and the manager's answer if there is one.
- Output (`TriageProposal`): category, labels (≤ 5), priority, story points (Fibonacci), duplicate (must be one of the similar tickets shown), confidence for classification and for sizing, a short reason, and an optional question.
- One Haiku 5.5 call, effort `low`, budget $0.05 per run. Estimated ~2K tokens in / 500 out → **~$0.0005 per ticket**, ~$0.00015 more per image.
- Code enforces limits on the answer: allowed values, snapped story points, duplicate only from the candidates, no second question.

## Run states
`queued → proposed → applied | dismissed`, or `queued → needs_answer → queued (with answer) → proposed`, or `failed`.

## Permissions
Project members see the latest run on a ticket. Only managers answer, accept (with edits), dismiss or re-run.

## Steps (commit after each)
- 4a Data model, agent, worker job, API, tests (fake Claude) + one live run
- 4b Ticket screen: triage panel (status, question and answer, suggestion with edits, cost), re-run
