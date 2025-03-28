ARG PYTHON_TAG=3.12
ARG CHAINLIT_PORT=8888

FROM python:${PYTHON_TAG} AS builder
# copy only the parts needed for production
COPY ./src/integrations ./src/integrations
COPY ./src/solutions ./src/solutions
COPY ./src/features ./src/features
COPY ./src/entrypoint ./src/entrypoint
# install dependencies and packages
COPY --from=ghcr.io/astral-sh/uv:0.5.15 /uv /uvx /bin/

ENV UV_PROJECT_ENVIRONMENT="/usr/local/"

RUN --mount=type=bind,source=./uv.lock,target=./uv.lock --mount=type=bind,source=./pyproject.toml,target=./pyproject.toml uv sync --python python${PYTHON_TAG} --locked --no-editable --no-python-downloads --link-mode copy --compile-bytecode --extra chat

FROM builder AS chat
COPY ./public/ ./public/
COPY ./.chainlit/ ./.chainlit/
COPY ./chainlit.md ./chainlit.md

CMD ["chainlit", "run", "./src/entrypoint/chat.py"]

EXPOSE ${CHAINLIT_PORT}
