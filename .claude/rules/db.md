---
paths:
  - "backend/app/db/**"
---
# Database

- Every schema change is a migration. Never edit a migration that has been applied.
- One concern per migration. Data migrations are separate from schema migrations.
- `NOT NULL` and foreign keys by default; a nullable column needs a reason.
- Timestamps are `timestamptz`, stored in UTC.
- Job queue: claim with `SELECT ... FOR UPDATE SKIP LOCKED`; claim and status update in one transaction.
- Vector columns: store the embedding model name and dimension next to them, and add an HNSW index on columns used for search.
- Load related rows explicitly. No N+1 queries.
- LangGraph checkpoint tables belong to LangGraph. Don't edit them by hand.
