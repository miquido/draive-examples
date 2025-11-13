from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Request, Response
from fastapi.routing import APIRoute
from haiway import ctx

from solutions.jwt import JWTVerification

__all__ = ("JWTAuthorizedAPIRoute",)


class JWTAuthorizedAPIRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        route_handler: Callable[[Request], Coroutine[Any, Any, Response]]
        route_handler = super().get_route_handler()

        async def authorized_route_handler(request: Request) -> Response:
            with ctx.updated(await JWTVerification.verify(request)):
                # allow accessing jwt payload in requests
                return await route_handler(request)

        return authorized_route_handler
