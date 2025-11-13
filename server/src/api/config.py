from typing import Final
from uuid import uuid4

from draive import (
    getenv_int,
    getenv_str,
)

__all__ = (
    "OTEL_ENVIRONMENT",
    "OTEL_EXPORTER_ENDPOINT",
    "OTEL_SERVICE_INSTANCE_ID",
    "SERVER_HOST",
    "SERVER_PORT",
    "SERVER_THREADS",
    "SERVER_WORKERS",
    "VERSION",
)

VERSION: Final[str] = getenv_str("VERSION", default="0.1.0")
SERVER_HOST: Final[str] = getenv_str(
    "SERVER_HOST",
    default="0.0.0.0",
)
SERVER_PORT: Final[int] = getenv_int(
    "SERVER_PORT",
    default=8888,
)
SERVER_WORKERS: Final[int] = getenv_int(
    "SERVER_WORKERS",
    default=2,
)
SERVER_THREADS: Final[int] = getenv_int(
    "SERVER_THREADS",
    default=1,
)
OTEL_EXPORTER_ENDPOINT: Final[str | None] = getenv_str("OTEL_EXPORTER_ENDPOINT")
OTEL_ENVIRONMENT: Final[str] = getenv_str("OTEL_ENVIRONMENT", default="undefined")
OTEL_SERVICE_INSTANCE_ID: Final[str] = getenv_str(
    "OTEL_SERVICE_INSTANCE_ID",
    default=getenv_str(
        "SERVICE_INSTANCE_ID",
        default=uuid4().hex,
    ),
)
