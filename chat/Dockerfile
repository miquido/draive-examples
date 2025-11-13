ARG PYTHON_TAG=3.13
ARG UNIT_TAG=1.34.2-python${PYTHON_TAG}-slim

# CHAT SERVER #

FROM unit:${UNIT_TAG} AS chat_builder
# copy only the parts needed for production
COPY ./src/integrations ./src/integrations
COPY ./src/solutions ./src/solutions
COPY ./src/features ./src/features
COPY ./src/chat ./src/chat
COPY ./public ./public
COPY .chainlit .chainlit
COPY ./chainlit.md ./chainlit.md
# install dependencies and packages
COPY --from=ghcr.io/astral-sh/uv:0.9.7 /uv /uvx /bin/

ENV UV_PROJECT_ENVIRONMENT="/usr/local/"
ENV PYTHONPATH="/src"

RUN --mount=type=bind,source=./uv.lock,target=./uv.lock \
  --mount=type=bind,source=./pyproject.toml,target=./pyproject.toml \
  uv sync --locked --link-mode copy --compile-bytecode --project ./ --extra chat

FROM chat_builder AS chat

# allow access to home directory for asyncpg library
RUN chgrp -R unit ${HOME} && chmod -R 050 ${HOME}

# allow access to chainlit directories
RUN mkdir .files
RUN chgrp -R unit .files && chmod -R 070 .files
RUN chgrp -R unit .chainlit && chmod -R 070 .chainlit

RUN apt-get update \
  && apt-get upgrade -y \
  && apt-get -y autoremove \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# copy configuration
COPY ./config/unit.json /docker-entrypoint.d/config.json

CMD ["unitd", "--no-daemon", "--log", "/dev/stdout"]

# port 80 is already exposed by nginx unit image, can't change it...

# Migrations service #

FROM python:${PYTHON_TAG} AS migrations_builder

# copy only the parts needed for production
COPY ./src/integrations ./src/integrations
COPY ./src/solutions ./src/solutions
COPY ./src/features ./src/features
COPY ./src/migrations ./src/migrations
# install dependencies and packages
COPY --from=ghcr.io/astral-sh/uv:0.9.7 /uv /uvx /bin/

ENV UV_PROJECT_ENVIRONMENT="/usr/local/"

RUN --mount=type=bind,source=./uv.lock,target=./uv.lock \
  --mount=type=bind,source=./pyproject.toml,target=./pyproject.toml \
  uv sync --locked --link-mode copy --compile-bytecode --project ./ --extra migrations

FROM migrations_builder AS migrations

RUN apt-get update \
  && apt-get upgrade -y \
  && apt-get -y autoremove \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

CMD ["python", "-m", "migrations"]
