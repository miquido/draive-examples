from typing import Literal, overload

from qdrant_client import AsyncQdrantClient

from integrations.qdrant.config import QDRANT_HOST, QDRANT_PORT

__all__ = [
    "QdrantSession",
]


class QdrantSession:
    __slots__ = (
        "_client",
        "_host",
        "_in_memory",
        "_port",
        "_ssl",
    )

    @overload
    def __init__(
        self,
        *,
        in_memory: Literal[True],
    ) -> None: ...

    @overload
    def __init__(
        self,
        *,
        host: str = QDRANT_HOST,
        port: int = QDRANT_PORT,
        ssl: bool = False,
        in_memory: Literal[False] = False,
    ) -> None: ...

    def __init__(
        self,
        *,
        host: str = QDRANT_HOST,
        port: int = QDRANT_PORT,
        ssl: bool = False,
        in_memory: bool = False,
    ) -> None:
        self._host = host
        self._port = port
        self._ssl = ssl
        self._in_memory = in_memory
        self._client: AsyncQdrantClient = self._prepare_client()

    def _prepare_client(self) -> AsyncQdrantClient:
        if self._in_memory:
            return AsyncQdrantClient(
                location=":memory",
            )

        else:
            return AsyncQdrantClient(
                host=self._host,
                port=self._port,
                https=self._ssl,
                prefer_grpc=True,
            )

    async def _open_session(self) -> None:
        await self._client.close()
        self._client = self._prepare_client()

    async def _close_session(self) -> None:
        await self._client.close()
