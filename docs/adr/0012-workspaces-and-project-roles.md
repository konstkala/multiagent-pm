# 0012. Workspaces, projects and per-project roles

Status: accepted, 2026-10-16

## Context
A manager runs several projects with different teams. The same person can manage one project and work on another. Different companies must never see each other's data.

## Decision
Workspace (company) → projects → project members, each with a role: `manager` or `employee`. Every query on project data is scoped by workspace and checked against the caller's role in that project, in the service layer.

## Consequences
- Realistic permissions, and one person can hold different roles.
- Every endpoint needs a membership check; a shared dependency does it, and tests cover access from outside the project.
