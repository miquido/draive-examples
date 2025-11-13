FROM debian:bookworm-slim AS build-base

ENV DEBIAN_FRONTEND=noninteractive \
  UV_PYTHON_INSTALL_DIR=/opt/python \
  UV_CACHE_DIR=/var/cache/uv

RUN apt-get update && \
  apt-get install -y --no-install-recommends \
  bash \
  build-essential \
  ca-certificates \
  curl \
  git \
  pkg-config \
  tar \
  xz-utils && \
  rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.9.9 /uv /uvx /usr/local/bin/

RUN mkdir -p /var/cache/uv && uv python install 3.13

WORKDIR /app

COPY uv.lock pyproject.toml ./
COPY src ./src

FROM build-base AS builder-migrations

RUN uv sync --locked --link-mode copy --compile-bytecode --project ./ --extra migrations && \
  rm -rf /var/cache/uv

FROM build-base AS builder-server

RUN uv sync --locked --link-mode copy --compile-bytecode --project ./ --extra server && \
  rm -rf /var/cache/uv


FROM debian:bookworm-slim AS runtime-base

ENV DEBIAN_FRONTEND=noninteractive \
  PYTHONPATH="/app/src" \
  PATH="/app/.venv/bin:$PATH"

RUN apt-get update && \
  apt-get install -y --no-install-recommends ca-certificates && \
  rm -rf /var/lib/apt/lists/*

RUN useradd --system --create-home --home-dir /app app

WORKDIR /app

FROM runtime-base AS api

COPY --from=builder-server /app/.venv /app/.venv
COPY --from=builder-server /app/src /app/src
COPY --from=builder-server /opt/python /opt/python

RUN chown -R app:app /app

EXPOSE 8080

USER app

ENV GRANIAN_WORKERS=2 \
  PYTHONOPTIMIZE=2

CMD ["/bin/sh", "-c", "exec /app/.venv/bin/granian api.application:app --host 0.0.0.0 --port 8080 --interface asgi --workers \"${GRANIAN_WORKERS}\" --access-log --log-level info"]

FROM runtime-base AS migrations

COPY --from=builder-migrations /app/.venv /app/.venv
COPY --from=builder-migrations /app/src /app/src
COPY --from=builder-migrations /opt/python /opt/python

RUN chown -R app:app /app

USER app

CMD ["/bin/sh", "-c", "/app/.venv/bin/python -B -m migrations"]
