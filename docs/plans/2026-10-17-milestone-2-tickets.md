# Milestone 2: the ticket experience

Parent: [product plan v1](2026-10-16-product-v1.md). Decisions 2026-10-17.

## Model changes (migration 0007)
- **Status**: `todo → in_progress → in_review → done`, plus `cancelled`. Existing values map: open→todo, resolved/closed→done.
- **Category** replaces `type`: `bug, implementation, improvement, analysis, task` (feature→implementation, question→analysis).
- **Assignee** becomes a real user (`assignee_id`), who must be a project member. The free-text column and `component` are dropped (labels cover the area).
- **Story points** (1, 2, 3, 5, 8, 13) and **due date**: nullable until a manager or the triage agent sets them.
- **Sub-tasks**: `parent_id`, one level deep, same project.
- **Links** (`ticket_links`): `blocks`, `relates_to`. `duplicate_of` stays a field (triage sets it).
- **Comments** (`ticket_comments`): authors edit and delete their own; managers can delete any.
- **Attachments** (`ticket_attachments`): metadata in Postgres, file in object storage.

## Permissions
| Action | Manager | Employee |
|---|---|---|
| Read tickets, comments, attachments in the project | ✓ | ✓ |
| Comment, attach | ✓ | ✓ |
| Create, copy, edit fields, assign, link, sub-tasks | ✓ | – |
| Move status between To do / In progress / In review | ✓ | own assigned tickets |
| Set Done or Cancelled, reopen | ✓ | – |
| Return to manager (unassign, back to To do, required reason) | – | own assigned tickets |

Enforced in the service layer; outsiders still get 404.

## Attachments
- MinIO (S3 API) in Docker locally; S3 or Cloudflare R2 in production. boto3 behind a small `Storage` interface.
- Upload through the API (multipart): one place for permission checks, a 10 MB limit and an allowed-types list (images, PDF, text, CSV, Office documents, ZIP). SVG and HTML are refused because browsers can run scripts in them.
- Downloads through the API after a permission check, with `Content-Disposition` and `nosniff`.
- Object keys are random; the original filename is stored separately and cleaned.

## UI
- **List**: filters (status, assignee, category, label), search, sorting.
- **Board**: columns per status, drag and drop to change status (permissions respected).
- **Detail**: title and description, fields sidebar, sub-tasks, links, comments, attachments; "Return to manager" for assignees; "Copy" for managers.

## Steps (commit after each)
- 2a Schema + ticket API (statuses, fields, permissions, sub-tasks, links, copy, return, filters, comments). **Done** (migration 0007 converts old data; 16 new tests)
- 2b Attachments with MinIO
- 2c List and detail pages
- 2d Board with drag and drop

## Not in this milestone
Activity history per ticket (audit logs exist; a visible history comes later), notifications, presigned direct uploads (an optimisation for large files).
