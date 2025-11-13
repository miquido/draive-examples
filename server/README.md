# AI server

Example of AI server exposing a chat feature.

Add `OPENAI_API_KEY` env variable to run using OpenAI services.

## Template highlights

- 100% Python stack with a modern `pyproject.toml` targeting Python 3.13, linters, formatters, and helpful `make`/CLI commands already wired up.
- Backend-only template: no UI assets, just a FastAPI application you can extend with your own functionality.
- Includes a minimal chat endpoint that streams tokens so you can see how to build assistant-like experiences.
- Serves HTTP traffic through FastAPI running on the high-performance Granian worker.
- Ships with a CLI that lets you hit the sample chat flow directly from your terminal.
- `Dockerfile` and `docker-compose.yml` are ready for local runs and container-based deployments out of the box.
- Postgres configuration (init SQL, model config) and in-memory fallbacks are provided, along with setup instructions inside `config/`.
- JWT-based authorization is built in: drop your JWK set into `AUTH_TOKEN_SETS` and every FastAPI route will enforce Bearer tokens automatically.
- Adding OpenTelemetry is as simple as defining a single environment variable pointing to your OTEL exporter URL.

## Make commands

- `make venv` – installs the pinned `uv` version, clones `.env`, prepares git hooks, and syncs a managed Python 3.13 virtualenv.
- `make sync` / `make update` – syncs or upgrades dependencies using `uv` so the lockfile stays authoritative.
- `make format` – applies Ruff fixes and formatting across `src/`.
- `make lint` – runs Bandit security checks, Ruff lint, and Pyright type analysis.
- `make api` – starts the FastAPI + Granian server (`python -m api`), perfect for local dev.
- `make cli` – launches the sample chat client; accepts `SESSION_ID` to resume conversations.
- `make docker_run` – rebuilds and runs the API service via Docker Compose; `make sidekicks` brings up Postgres helpers.
- `make migrations` – executes `python -m migrations` so schema changes stay in sync with Postgres.

## Authorization

- All API routes are wrapped with `JWTAuthorizedAPIRoute`, so requests must send `Authorization: Bearer <token>` headers containing RS256 JWTs with `iss`, `aud`, and `exp` claims.
- Point the server at your signing keys by setting `AUTH_TOKEN_SETS` to a JSON Web Key Set (see `config/.env.example` for the format). Rotating keys is just a matter of updating that env var and restarting.
- For the bundled CLI you can either paste a ready-made token into `CLI_API_TOKEN` or let it mint one on the fly by providing `AUTH_TOKEN_PRIVATE_KEY` (PEM string), `AUTH_TOKEN_ISSUER`, and `AUTH_TOKEN_AUDIENCE`.
- Custom clients only need to generate a compatible JWT (matching the issuer/audience and any extra claims you enforce) and include it in the `Authorization` header, making it easy to hook the template into your own IAM or identity provider.
