from types import TracebackType
from typing import final

from integrations.qdrant.search import QdrantSearchMixin
from integrations.qdrant.session import QdrantSession
from integrations.qdrant.state import Qdrant
from integrations.qdrant.store import QdrantStoreMixin

__all__ = [
    "QdrantClient",
]


@final
class QdrantClient(
    QdrantSearchMixin,
    QdrantStoreMixin,
    QdrantSession,
):
    async def __aenter__(self) -> Qdrant:
        await self._open_session()
        return Qdrant(
            collection_creating=self.create_collection,
            collection_deleting=self.delete_collection,
            collection_index_creating=self.create_index,
            storing=self.store,
            fetching=self.fetch,
            searching=self.search,
            deleting=self.delete,
        )

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self._close_session()
