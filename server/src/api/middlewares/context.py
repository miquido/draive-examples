import traceback
from collections.abc import Mapping, MutableMapping

from draive import Observability, ctx
from haiway.opentelemetry import OpenTelemetry
from starlette.datastructures import MutableHeaders
from starlette.exceptions import HTTPException, WebSocketException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

__all__ = ("ContextMiddleware",)


class ContextMiddleware:
    def __init__(
        self,
        app: ASGIApp,
    ) -> None:
        self.app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        with ctx.presets(*scope["app"].extra.get("presets", ())):
            observability: Observability | None
            if scope["app"].extra.get("otel", False):
                observability = OpenTelemetry.observability(traceparent=_request_traceparent(scope))

            else:
                observability = None

            if scope["type"] == "http":
                return await self._handle_http(
                    scope=scope,
                    receive=receive,
                    send=send,
                    observability=observability,
                )

            elif scope["type"] == "websocket":
                return await self._handle_websocket(
                    scope=scope,
                    receive=receive,
                    send=send,
                    observability=observability,
                )

            else:
                return await self.app(scope, receive, send)

    async def _handle_http(
        self,
        *,
        scope: Scope,
        receive: Receive,
        send: Send,
        observability: Observability | None,
    ) -> None:
        async with ctx.scope(
            f"{scope['method']} {scope['path']}",
            *scope["app"].extra.get("state", ()),
            observability=observability,
        ) as trace_id:
            response_headers: Mapping[str, str]
            if traceparent := OpenTelemetry.traceparent():
                response_headers = {
                    "trace_id": trace_id,
                    "traceparent": traceparent,
                }

            else:
                response_headers = {
                    "trace_id": trace_id,
                }

            async def traced_send(message: Message) -> None:
                if message["type"] == "http.response.start":
                    headers = MutableHeaders(scope=message)
                    headers.update(response_headers)

                await send(message)

            try:
                return await self.app(
                    scope,
                    receive,
                    traced_send,
                )

            except HTTPException as exc:
                if exc.headers is None:
                    exc.headers = response_headers

                elif isinstance(exc.headers, MutableMapping):
                    exc.headers.update(response_headers)

                raise exc  # do not change behavior for HTTPException

            except BaseException as exc:
                error_type: type[BaseException] = type(exc)

                error_message: str
                if __debug__:
                    error_message = (
                        f"{error_type.__name__} [{error_type.__module__}]:"
                        f" {exc} - that is an error!"
                        f"\n{traceback.format_exc()}"
                    )

                else:
                    error_message = (
                        f"{error_type.__name__} [{error_type.__module__}] - that is an error!"
                    )

                ctx.log_error(
                    f"Internal server error: {exc}",
                    exception=exc,
                )

                raise HTTPException(
                    status_code=500,
                    headers=response_headers,
                    detail=error_message,
                ) from exc

    async def _handle_websocket(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        observability: Observability | None,
    ) -> None:
        async with ctx.scope(
            f"WS {scope['path']}",
            *scope["app"].extra.get("state", ()),
            observability=observability,
        ):
            try:
                return await self.app(scope, receive, send)

            except WebSocketException as exc:
                raise exc

            except BaseException as exc:
                error_type: type[BaseException] = type(exc)

                error_message: str
                if __debug__:
                    error_message = (
                        f"{error_type.__name__} [{error_type.__module__}]:"
                        f" {exc} - that is an error!"
                        f"\n{traceback.format_exc()}"
                    )

                else:
                    error_message = (
                        f"{error_type.__name__} [{error_type.__module__}] - that is an error!"
                    )

                ctx.log_error(
                    error_message,
                    exception=exc,
                )

                raise WebSocketException(
                    code=1011,
                    reason=error_message,
                ) from exc


def _request_traceparent(scope: Scope) -> str | None:
    for raw_name, raw_value in scope.get("headers") or ():
        if raw_name not in (b"traceparent", b"Traceparent"):
            continue

        try:
            return raw_value.decode("ascii").strip()

        except UnicodeDecodeError:
            return None

    return None
