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
| **argon2id** | Password hashing algorithm, slow on purpose | Makes stolen password hashes expensive to crack; OWASP's first choice |
| **Session cookie (opaque token)** | A random token the browser sends back on each request | Revocable (sign out everywhere), unlike a JWT; only its hash is stored |
| **httpOnly / Secure / SameSite** | Cookie flags | Scripts can't read it (XSS), HTTPS only, not sent on cross-site POSTs |
| **CSRF** | Another site making your browser send a request to ours | Blocked by SameSite plus a required custom header |
| **CORS** | Browser rule for which sites may call our API | Only our frontend's origin may send credentialed requests |
| **Account enumeration** | Learning which emails have accounts from responses or timing | Same messages and similar timing for known and unknown emails |
| **Rate limiting (fixed window)** | Counting attempts per key per time window | Slows password guessing; stored in Postgres to work across replicas |
| **Mailpit** | A fake SMTP server with a web inbox | Test real emails locally without sending anything |
| **Multi-tenancy** | Many companies (tenants) sharing one app and database | Every query is scoped by workspace/project so data never leaks between them |
| **RBAC (role-based access control)** | Permissions come from a role (manager, employee) | Simple rules per project; checked in the service layer, not the UI |
| **404 instead of 403** | Hiding that a resource exists | "Forbidden" would confirm a project is real; "not found" reveals nothing |
| **Atomic counter (`UPDATE ... RETURNING`)** | Increment and read in one statement | Two tickets created at once never get the same number |
| **JSON logging** | One JSON object per log line | Log tools can search and filter by field (`request_id`, `status`) |
| **Request ID** | Unique id per HTTP request | Follow one request through all logs |
| **Liveness / readiness** | Two kinds of health check | Liveness: restart if dead. Readiness: send traffic only when the DB is ready |
| **ADR** | Architecture Decision Record | One file per decision: context, choice, consequences |

### Frontend and sign-in

| Tech | What it is | Why we use it |
|---|---|---|
| **React** | A library for building UI from components | Every screen is React components |
| **Next.js** | A framework on top of React: routing, server rendering, proxy, production server | Pages from folders, `/api` proxy, a self-contained server for Docker |
| **Server vs client components** | Server: rendered on the server, no browser JS. Client (`"use client"`): interactive | Static shells are fast; forms and signed-in data are client components |
| **Tailwind CSS** | Utility classes in the markup | Fast, consistent styling without separate CSS files |
| **TanStack Query** | Library for server data in React: caching, loading/error state, refetch | No hand-written loading logic; mutations refresh exactly what they change |
| **OpenAPI codegen** | Types and client generated from the API schema | Frontend and backend can't silently disagree on request/response shapes |
| **Reverse proxy** | A server that forwards requests to another server | `/api` on the frontend reaches FastAPI; one origin for the browser |
| **X-Forwarded-For** | Header a proxy adds with the original client address | Rate limits see the real user, not the proxy; trust it only from your proxy |
| **OAuth 2.0 / OpenID Connect** | Standards for "sign in with Google" | Google proves who the user is; we never see their Google password |
| **ID token (JWT)** | A signed token from Google stating who signed in | We check signature, issuer, audience, expiry and nonce before trusting it |
| **PKCE** | A one-time secret proving the code exchange comes from whoever started sign-in | A stolen authorization code is useless on its own |
| **state / nonce** | Random values tying Google's answer to this browser and this attempt | Stops login CSRF and token replay |

### Background work

| Tech | What it is | Why we use it |
|---|---|---|
| **Job queue** | A table of work to do later, picked up by workers | Slow or failure-prone work (AI calls) never blocks a web request |
| **SELECT … FOR UPDATE SKIP LOCKED** | Lock a row and skip rows others have locked | Many workers can pull from one queue without ever taking the same job |
| **At-least-once delivery** | A job may run twice (e.g. a worker dies after finishing) | Handlers are written to be safe to repeat |
| **Exponential backoff** | Wait 30 s, 60 s, 120 s… between retries | Gives a struggling dependency time to recover instead of hammering it |
| **Graceful shutdown (SIGTERM)** | Finish current work, then exit, when asked to stop | Deploys and scaling don't cut jobs in half |
| **Flaky test** | A test that sometimes fails with no code change | Usually a hidden timing assumption; fix the assumption, don't retry the test |

### AI agents and privacy

| Tech | What it is | Why we use it |
|---|---|---|
| **Structured output** | The model must answer in a given JSON schema, validated into a Pydantic object | No parsing free text; a bad answer fails loudly |
| **PDF input** | Claude reads a PDF directly (text + page images) | No PDF parsing library needed; layout is understood |
| **Prompt injection** | Text inside data (a CV, a ticket) that tries to give the model orders | Treated as data in the prompt; no tools to misuse; a person reviews the result |
| **Human in the loop** | A person approves before an AI result takes effect | The manager is accountable for profiles; EU rules treat CV-based decisions as high-risk |
| **Data minimisation (GDPR)** | Keep personal data only as long as needed | The CV is deleted after reading; the draft after the decision |
| **Correlation id** | One id on every log line of a request or job | One search shows the whole story; never overwrite it |
| **Confidence threshold (auto-apply)** | The model rates how sure it is; code acts alone only above a cut-off | Triage sets category and labels by itself at ≥ 0.7 and only on empty fields; the rest waits for a manager |
| **Clarifying question** | The agent asks once instead of guessing, then runs again with the answer | Better sizing for vague tickets, for the cost of one more cheap call |
| **Clock skew** | Two machines (or a container and its host) disagree on the time | Our DB clock was 0.3 s ahead, so new jobs looked "not due yet". Fix: take all queue times from one clock |
| **Scoring vs generation** | Code computes the decision; the LLM only puts it into words | Assignment ranking is testable, explainable and free; Haiku writes the reasons |
| **Pseudonymisation** | Replace who someone is with a stand-in (A, B, C) before sharing data | The model never sees names, so it can't leak them or be swayed by them |
| **Hit rate (top-k accuracy)** | How often the person picks the agent's first choice (top-1) or one of its 3 (top-3) | Recorded on every assignment: the honest test of whether the agent helps |
| **Head-of-line blocking** | A quick task stuck behind slow ones in a single FIFO line | A click waited 14 s behind triage jobs; job priority brought it to 4 s |
| **Job priority** | Queue order by urgency first, then age (lower runs first, like Unix `nice`) | Interactive jobs beat background work |

### Tickets and files

| Tech | What it is | Why we use it |
|---|---|---|
| **Object storage (S3 API)** | Files stored as objects in buckets, reached over HTTP | Files don't bloat the database; the S3 API is the standard every cloud speaks |
| **SeaweedFS** | An open-source server that speaks the S3 API | Local stand-in for S3 after MinIO stopped publishing images |
| **boto3** | AWS's Python SDK | Talks to S3, R2 or SeaweedFS with the same code |
| **Content sniffing / magic bytes** | Recognising a file by its first bytes, not its name | A file named `.png` that is really HTML is refused |
| **CSP `sandbox`** | A header telling the browser to run nothing from this response | Even if someone opens a downloaded file in the browser, its scripts can't run |
| **Optimistic update** | Show the change first, confirm with the server after | The board feels instant; a refused move jumps back with the reason |
| **dnd-kit** | Accessible drag-and-drop for React | Board cards move by mouse, touch or keyboard |
| **URL as state** | Filters stored in the address bar | A filtered view can be bookmarked or shared, and Back works |

## Planned (not used yet)

| Tech | What it is | Why we'll use it |
|---|---|---|
| **LangGraph** | Agent workflow framework | Graph of steps, checkpoints, human approval pauses |
| **PydanticAI** | Typed LLM agents | Structured, validated LLM outputs |
| **Claude API** | Anthropic's LLM API | Haiku for workers, Sonnet for planning |
| **Langfuse** | LLM observability | Traces, tokens, $ per run |
| **GitHub Actions** | CI/CD service | Run checks on every push and PR |
| **Terraform** | Infrastructure as Code | Cloud resources defined in files, reviewed like code |
