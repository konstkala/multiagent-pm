# Logging

Goal: anyone can trace what happened, who or what did it, and why, without the logs leaking data.

- Use `logging.getLogger(__name__)` + `core/logging`. JSON lines only. No `print`.
- The message is a stable event name `area.action` (`http.request`, `llm.call`, `triage.classified`). Details go in `extra=log_fields(...)`, never formatted into the message.
- Every line carries a correlation id: `request_id` for HTTP (set by the middleware), `run_id` for jobs (set by the worker). Never overwrite these from a log call; name other ids explicitly (`budget_id`, `import_id`).
- Log at the boundaries:
  - HTTP request: method, path, status, duration
  - job: start, end, failure
  - LLM call: model, tokens, $, latency, stop_reason
  - tool call: name, outcome
  - external calls; startup and shutdown
- Audit every state change as `audit.<action>`: actor (user or agent), action, target id, before → after.
- Security events at WARNING: auth failures, permission denials, budget-cap hits, refusals, rejected input, suspected prompt injection.
- Never log secrets, tokens, passwords, full prompts, ticket or user text, or query strings. Log ids and lengths instead. Redaction in `core/logging` is a backstop, not permission.
- Levels: DEBUG for noise (health probes), INFO for normal events, WARNING for handled problems, ERROR for failures that need attention (with the traceback).
- Log an error once, where it's handled, with `logger.exception`. Don't log and re-raise at every layer.
- No logging inside tight loops: log a summary after.
