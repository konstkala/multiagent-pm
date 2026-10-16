# 0014. Story points and due dates for difficulty

Status: accepted, 2026-10-16

## Context
Tickets need a difficulty for workload balancing and a date for the calendar.

## Decision
Story points on the Fibonacci scale (1, 2, 3, 5, 8, 13), estimated by the triage agent and approved by a manager, plus an optional due date. Workload is open points per person.

## Consequences
- Familiar to anyone who has used Jira; avoids hour estimates that feel like time tracking.
- Estimate accuracy (points vs actual cycle time) becomes a KPI and the main measure of the triage agent.
