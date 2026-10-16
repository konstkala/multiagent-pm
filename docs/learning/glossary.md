# Glossary: what we use and why

A few words each. New technologies are added as they appear.

| Tech | What it is | Why we use it |
|---|---|---|
| **Python 3.12** | Programming language | AI/agent libraries ship in Python first |
| **uv** | Python package + environment manager | Fast installs; `uv.lock` pins exact versions everywhere |
| **FastAPI** | Async web framework | Typed endpoints, auto docs at `/docs`, OpenAPI schema for the frontend client |
| **Pydantic** | Data validation from type hints | Validates requests, LLM outputs, tool inputs |
| **pydantic-settings** | Config from env vars / `.env` | One typed `Settings` object; secrets stay out of code (12-factor) |
| **Uvicorn** | ASGI server | Runs the FastAPI app (`fastapi dev` uses it) |
| **PostgreSQL 17** | Relational database | One DB for data, vectors, agent checkpoints, job queue |
| **pgvector** | Postgres extension for vectors | Similar-ticket search without a separate vector DB |
| **SQLAlchemy 2** | ORM + SQL toolkit | Typed models and queries in Python, async |
| **asyncpg** | Async Postgres driver | What SQLAlchemy uses to talk to Postgres; fast, works on Windows |
| **Alembic** | Schema version control | Numbered migration files; same schema on laptop, CI, prod |
| **Docker / Compose** | Containers / multi-container runner | Same Postgres for everyone, no local install; `docker compose up -d db` |
| **pytest** | Test runner | Tests + markers (`db`, `llm`) to choose what runs |
| **pytest-asyncio** | Async support for pytest | Our code is async, so tests are too |
| **httpx** | HTTP client | Calls the app in tests without starting a server |
| **ruff** | Linter + formatter | Catches bugs and keeps one code style, very fast |
| **pyright** | Static type checker | Catches type errors before runtime (strict mode) |
| **Anthropic SDK** | Official Python client for the Claude API | Typed requests/responses, retries, timeouts; wrapped by `core/llm` so nothing else imports it |
| **Prompt caching** | Server caches a stable prompt prefix | Cached tokens cost ~10% of normal input; the system prompt is marked cacheable |
| **Effort** | Claude setting for how much the model thinks | Lower effort = fewer tokens, lower cost and latency; set per call |
| **Fake / test double** | A stand-in object used in tests | Tests exercise our gateway without paid API calls |
| **JSON logging** | One JSON object per log line | Log tools can search and filter by field (`request_id`, `status`) |
| **Request ID** | Unique id per HTTP request | Follow one request through all logs |
| **Liveness / readiness** | Two kinds of health check | Liveness: restart if dead. Readiness: send traffic only when the DB is ready |
| **ADR** | Architecture Decision Record | One file per decision: context, choice, consequences |

## Planned (not used yet)

| Tech | What it is | Why we'll use it |
|---|---|---|
| **LangGraph** | Agent workflow framework | Graph of steps, checkpoints, human approval pauses |
| **PydanticAI** | Typed LLM agents | Structured, validated LLM outputs |
| **Claude API** | Anthropic's LLM API | Haiku for workers, Sonnet for planning |
| **Langfuse** | LLM observability | Traces, tokens, $ per run |
| **fastembed** | Local embedding model | Turns tickets into vectors for free |
| **Next.js** | React framework | Frontend with server + client components |
| **GitHub Actions** | CI/CD service | Run checks on every push and PR |
| **Terraform** | Infrastructure as Code | Cloud resources defined in files, reviewed like code |
