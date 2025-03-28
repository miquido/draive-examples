from collections.abc import Iterable, Sequence
from typing import Literal, overload

from draive import AttributeRequirement, DataModel, Embedded, State, ctx

from integrations.qdrant.types import (
    QdrantCollectionCreating,
    QdrantCollectionDeleting,
    QdrantDeleting,
    QdrantFetching,
    QdrantPaginationResult,
    QdrantPaginationToken,
    QdrantResult,
    QdrantSearching,
    QdrantStoring,
)

__all__ = [
    "Qdrant",
]


class Qdrant(State):
    @classmethod
    async def create_collection[Model: DataModel](
        cls,
        model: type[Model],
        /,
        *,
        vector_size: int,
        in_ram: bool = False,
        skip_existing: bool = False,
    ) -> bool:
        return await ctx.state(cls).collection_creating(
            model,
            vector_size=vector_size,
            in_ram=in_ram,
            skip_existing=skip_existing,
        )

    @classmethod
    async def delete_collection[Model: DataModel](
        cls,
        model: type[Model],
        /,
    ) -> None:
        return await ctx.state(cls).collection_deleting(model)

    @overload
    @classmethod
    async def fetch[Model: DataModel](
        cls,
        model: type[Model],
        /,
        *,
        requirements: AttributeRequirement[Model] | None = None,
        limit: int = 32,
        continuation: QdrantPaginationToken | None = None,
        return_vector: Literal[True],
    ) -> QdrantPaginationResult[Embedded[Model]]: ...

    @overload
    @classmethod
    async def fetch[Model: DataModel](
        cls,
        model: type[Model],
        /,
        *,
        requirements: AttributeRequirement[Model] | None = None,
        limit: int = 32,
        continuation: QdrantPaginationToken | None = None,
    ) -> QdrantPaginationResult[Model]: ...

    @classmethod
    async def fetch[Model: DataModel](
        cls,
        model: type[Model],
        /,
        *,
        requirements: AttributeRequirement[Model] | None = None,
        continuation: QdrantPaginationToken | None = None,
        limit: int = 32,
        return_vector: bool = False,
    ) -> QdrantPaginationResult[Embedded[Model]] | QdrantPaginationResult[Model]:
        return await ctx.state(cls).fetching(
            model,
            requirements=requirements,
            continuation=continuation,
            limit=limit,
            return_vector=return_vector,
        )

    @overload
    @classmethod
    async def search[Model: DataModel](
        cls,
        model: type[Model],
        /,
        *,
        query_vector: Sequence[float],
        requirements: AttributeRequirement[Model] | None = None,
        score_threshold: float | None = None,
        limit: int = 8,
        return_vector: Literal[True],
    ) -> Sequence[QdrantResult[Model]]: ...

    @overload
    @classmethod
    async def search[Model: DataModel](
        cls,
        model: type[Model],
        /,
        *,
        query_vector: Sequence[float],
        score_threshold: float | None = None,
        limit: int = 8,
    ) -> Sequence[Model]: ...

    @classmethod
    async def search[Model: DataModel](  # noqa: PLR0913
        cls,
        model: type[Model],
        /,
        *,
        query_vector: Sequence[float],
        requirements: AttributeRequirement[Model] | None = None,
        score_threshold: float | None = None,
        limit: int = 8,
        return_vector: bool = False,
    ) -> Sequence[QdrantResult[Model]] | Sequence[Model]:
        return await ctx.state(cls).searching(
            model,
            query_vector=query_vector,
            requirements=requirements,
            score_threshold=score_threshold,
            limit=limit,
            return_vector=return_vector,
        )

    @classmethod
    async def store[Model: DataModel](
        cls,
        model: type[Model],
        /,
        *,
        objects: Iterable[Embedded[Model]],
        batch_size: int = 64,
        max_retries: int = 3,
        parallel_tasks: int = 1,
    ) -> None:
        return await ctx.state(cls).storing(
            model,
            objects=objects,
            batch_size=batch_size,
            max_retries=max_retries,
            parallel_tasks=parallel_tasks,
        )

    @classmethod
    async def delete[Model: DataModel](
        cls,
        model: type[Model],
        /,
        *,
        requirements: AttributeRequirement[Model] | None = None,
    ) -> None:
        return await ctx.state(cls).deleting(
            model,
            requirements=requirements,
        )

    collection_creating: QdrantCollectionCreating
    collection_deleting: QdrantCollectionDeleting
    fetching: QdrantFetching
    searching: QdrantSearching
    storing: QdrantStoring
    deleting: QdrantDeleting
