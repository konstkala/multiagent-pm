# Multiagent PM

Smart project management, run by a team of AI agents.

## Quick start

```sh
docker compose up -d db          # Postgres 17 + pgvector
cd backend
uv sync
cp .env.example .env
uv run alembic upgrade head
uv run fastapi dev app/main.py   # http://localhost:8000/docs
```

More: [CLAUDE.md](CLAUDE.md) (stack, commands, principles), [docs/adr/](docs/adr/) (decisions), [docs/plans/](docs/plans/) (plans), [docs/learning/roadmap.md](docs/learning/roadmap.md).
