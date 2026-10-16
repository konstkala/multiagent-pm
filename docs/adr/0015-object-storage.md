# 0015. Attachments in S3-compatible object storage

Status: accepted, 2026-10-17

## Context
Tickets need file attachments (screenshots, documents as proof of work). Files don't belong in Postgres: they bloat backups and the database's memory. The plan named MinIO for local development, but MinIO no longer publishes its community Docker images (every tag we tried was gone).

## Decision
- Code talks plain S3 through boto3 behind a small `Storage` interface, never a specific product.
- Locally: SeaweedFS (`chrislusf/seaweedfs:4.00`), one container with an S3 endpoint. Production: AWS S3 or Cloudflare R2, configured by env vars.
- Uploads go through the API (permission check, 10 MB limit, type detected from content, random object keys). Downloads go through the API too, with `Content-Disposition`, `nosniff` and `CSP: sandbox`.

## Consequences
- Swapping the storage product is a configuration change; this happened once already.
- Every byte passes through the API. Fine at 10 MB; for large files, presigned direct uploads are the next step.
- Deleting a row and its object can't be one transaction. Failures are logged as `storage.orphan_object` for a cleanup job.
