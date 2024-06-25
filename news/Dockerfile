ARG PYTHON_TAG=3.12
ARG CHAINLIT_PORT=8888

FROM python:${PYTHON_TAG} as builder
# copy only the parts needed for production
COPY ./src/integrations ./src/integrations
COPY ./src/solutions ./src/solutions
COPY ./src/features ./src/features
COPY ./src/entrypoint ./src/entrypoint
# install dependencies and packages
RUN --mount=type=bind,source=./constraints,target=./constraints --mount=type=bind,source=./pyproject.toml,target=./pyproject.toml --mount=type=bind,source=./Makefile,target=./Makefile make install UV_ALIAS=/root/.cargo/bin/uv INSTALL_OPTIONS="."

FROM builder as chat 
COPY ./public/ ./public/
COPY ./.chainlit/ ./.chainlit/
COPY ./chainlit.md ./chainlit.md

CMD ["chainlit", "run", "./src/entrypoint/chat.py"]

EXPOSE ${CHAINLIT_PORT}
