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
| **UUID** | 128-bit random identifier | Ticket ids that can't be guessed or enumerated, unlike 1, 2, 3 |
| **CHECK constraint** | A rule the database enforces on a column | Bad `status` values are rejected even if the app has a bug |
| **Pagination** | Returning big lists in pages (`limit`, `offset`) | Keeps responses small and fast; `total` lets a UI show page counts |
| **Audit log** | Record of who changed what | Traceability; ours logs changed field names, never ticket text |
| **Transaction rollback in tests** | Undo each test's database changes | Tests stay independent and fast without recreating the database |
| **Multi-stage build** | A Dockerfile with several `FROM` stages | Build tools stay in the first stage; only the result is copied into the final image |
| **Layer cache** | Docker reuses unchanged build steps | Dependencies are copied before code, so code edits rebuild in seconds |
| **Non-root user** | The container process isn't `root` | If the app is compromised, the attacker has fewer rights |
| **.dockerignore** | Files excluded from the build | Keeps `.env`, `.venv` and tests out of the image |
| **Migration job** | A one-off container that runs migrations and exits | Schema is updated before the new API starts; same idea as a Kubernetes Job |
| **Embedding** | A list of numbers that represents the meaning of a text | Similar meaning gives nearby vectors, so we can find duplicate tickets by distance |
| **fastembed + ONNX** | Small library + model format that runs an embedding model on the CPU | Free and local; no API key; ~16 ms for a few short texts |
| **Cosine similarity** | How closely two vectors point the same way (1 = same meaning) | The metric bge models are trained for; our `min_similarity` cut-off uses it |
| **HNSW index** | Graph index for approximate nearest-neighbour search | Keeps similar-ticket queries fast as tickets grow, at a small recall cost |
| **Dependency injection (FastAPI `Depends`)** | The framework passes in what a function needs | Tests swap the real embedder for a fake without touching the code |
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
| **Next.js** | React framework | Frontend with server + client components |
| **GitHub Actions** | CI/CD service | Run checks on every push and PR |
| **Terraform** | Infrastructure as Code | Cloud resources defined in files, reviewed like code |
