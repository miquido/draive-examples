from typing import Final

from draive import getenv_int, getenv_str

__all__ = (
    "API_BASE_URL",
    "API_TOKEN",
    "AUTH_TOKEN_AUDIENCE",
    "AUTH_TOKEN_ISSUER",
    "AUTH_TOKEN_PRIVATE_KEY",
    "SERVER_HOST",
    "SERVER_PORT",
)

SERVER_HOST: str = getenv_str(
    "SERVER_HOST",
    default="127.0.0.1",
)
SERVER_PORT: int = getenv_int(
    "SERVER_PORT",
    default=8888,
)


API_BASE_URL: Final[str] = getenv_str(
    "CLI_API_BASE_URL",
    default=f"http://{SERVER_HOST}:{SERVER_PORT}",
)
API_TOKEN: Final[str | None] = getenv_str(
    "CLI_API_TOKEN",
)
AUTH_TOKEN_PRIVATE_KEY: Final[str] = getenv_str(
    "AUTH_TOKEN_PRIVATE_KEY",
    required=True,
)
AUTH_TOKEN_ISSUER: Final[str] = getenv_str(
    "AUTH_TOKEN_ISSUER",
    default="issuer",
)
AUTH_TOKEN_AUDIENCE: Final[str] = getenv_str(
    "AUTH_TOKEN_AUDIENCE",
    default="audience",
)
