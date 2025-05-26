from collections.abc import Iterable, Sequence
from typing import cast
from uuid import uuid4

from draive import AttributeRequirement, DataModel, Embedded, as_dict, as_list
from qdrant_client.models import (
    CollectionsResponse,
    Distance,
    Filter,
    FilterSelector,
    PointStruct,
    VectorParams,
)

from integrations.qdrant.filters import prepare_filter
from integrations.qdrant.session import QdrantSession
from integrations.qdrant.types import QdrantPaginationResult, QdrantPaginationToken

__all__ = [
    "QdrantStoreMixin",
]


class QdrantStoreMixin(QdrantSession):
    async def existing_collections(self) -> Sequence[str]:
        current_collections: CollectionsResponse = await self._client.get_collections()
        return tuple(collection.name for collection in current_collections.collections)

    async def create_collection[Model: DataModel](
        self,
        model: type[Model],
        /,
        *,
        vector_size: int,
        in_ram: bool,
        skip_existing: bool,
    ) -> bool:
        if skip_existing and await self._client.collection_exists(collection_name=model.__name__):
            return False

        return await self._client.create_collection(
            collection_name=model.__name__,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE,
                on_disk=not in_ram,
            ),
            on_disk_payload=not in_ram,
        )

    async def delete_collection[Model: DataModel](
        self,
        model: type[Model],
        /,
    ) -> None:
        await self._client.delete_collection(collection_name=model.__name__)

    async def fetch[Model: DataModel](
        self,
        model: type[Model],
        /,
        *,
        requirements: AttributeRequirement[Model] | None,
        continuation: QdrantPaginationToken | None,
        limit: int,
        return_vector: bool,
    ) -> QdrantPaginationResult[Embedded[Model]] | QdrantPaginationResult[Model]:
        records, next_point_id = await self._client.scroll(  # pyright: ignore[reportUnknownMemberType]
            collection_name=model.__name__,
            scroll_filter=prepare_filter(
                requirements=requirements,
            ),
            limit=limit,
            offset=continuation.next_id if continuation else None,
            with_payload=True,
        )

        continuation_token: QdrantPaginationToken | None
        if next_point_id is not None:
            continuation_token = QdrantPaginationToken(next_id=next_point_id)

        else:
            continuation_token = None

        if return_vector:
            return QdrantPaginationResult[Embedded[model]](
                results=[
                    Embedded[model](
                        value=model.from_mapping(record.payload),
                        # we ar using only a single vector
                        vector=cast(list[float], record.vector),
                    )
                    for record in records
                    if record.payload
                ],
                continuation_token=continuation_token,
            )

        else:
            return QdrantPaginationResult[model](
                results=[
                    model.from_mapping(record.payload)
                    for record in records
                    if record.payload is not None
                ],
                continuation_token=continuation_token,
            )

    async def store[Model: DataModel](
        self,
        model: type[Model],
        /,
        *,
        objects: Iterable[Embedded[Model]],
        batch_size: int,
        max_retries: int,
        parallel_tasks: int,
    ) -> None:
        self._client.upload_points(
            collection_name=model.__name__,
            points=[
                PointStruct(
                    id=uuid4().hex,
                    payload=as_dict(element.value.to_mapping()),
                    vector=as_list(element.vector),
                )
                for element in objects
            ],
            batch_size=batch_size,
            max_retries=max_retries,
            parallel=parallel_tasks,
        )

    async def delete[Model: DataModel](
        self,
        model: type[Model],
        /,
        *,
        requirements: AttributeRequirement[Model] | None,
    ) -> None:
        await self._client.delete(
            collection_name=model.__name__,
            points_selector=FilterSelector(
                filter=prepare_filter(
                    requirements=requirements,
                )
                or Filter(),
            ),
            wait=True,
        )
