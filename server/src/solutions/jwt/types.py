from collections.abc import Mapping
from typing import Any, Protocol

from haiway import State
from starlette.requests import Request
from typing_extensions import runtime

__all__ = (
    "JWTForbidden",
    "JWTSessionClaims",
    "JWTUnauthorized",
    "JWTVerifying",
)


@runtime
class JWTVerifying(Protocol):
    async def __call__(
        self,
        request: Request,
        claims: Mapping[str, str] | None = None,
    ) -> Mapping[str, Any]: ...


class JWTSessionClaims(State):
    claims: Mapping[str, Any]


class JWTUnauthorized(Exception):
    pass


class JWTForbidden(Exception):
    pass
