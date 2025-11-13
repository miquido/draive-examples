from collections.abc import Mapping
from typing import Any

from draive import ctx
from haiway import State
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from solutions.jwt.types import JWTForbidden, JWTSessionClaims, JWTUnauthorized, JWTVerifying

__all__ = ("JWTVerification",)


async def _undefined(
    request: Request,
    claims: Mapping[str, str] | None = None,
) -> Mapping[str, Any]:
    raise NotImplementedError("JWTVerification is not defined")


class JWTVerification(State):
    @classmethod
    async def verify(
        cls,
        request: Request,
        claims: Mapping[str, str] | None = None,
    ) -> JWTSessionClaims:
        session_claims: Mapping[str, Any]
        try:
            session_claims = await ctx.state(cls).jwt_verifying(
                request=request,
                claims=claims,
            )

        except JWTUnauthorized as exc:
            ctx.log_warning(
                "Invalid JWT authorization",
                exception=exc,
            )
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

        except JWTForbidden as exc:
            ctx.log_warning(
                "Invalid JWT authorization",
                exception=exc,
            )
            raise HTTPException(
                status_code=HTTP_403_FORBIDDEN,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

        else:
            return JWTSessionClaims(claims=session_claims)

    jwt_verifying: JWTVerifying = _undefined
