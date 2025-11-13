from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Literal, Protocol, Self, runtime_checkable
from uuid import UUID

from draive import AttributePath, AttributeRequirement, DataModel, Embedded, State
from qdrant_client.conversions.common_types import ScoredPoint

__all__ = [
    "QdrantCollectionCreating",
    "QdrantCollectionDeleting",
    "QdrantCollectionIndexCreating",
    "QdrantDeleting",
    "QdrantException",
    "QdrantFetching",
    "QdrantPaginationResult",
    "QdrantPaginationToken",
    "QdrantResult",
    "QdrantSearching",
    "QdrantStoring",
]


class QdrantResult[Content: DataModel](State):
    identifier: UUID
    vector: Mapping[str, Sequence[float]] | Sequence[float]
    score: float
    content: Content

    @classmethod
    def of(
        cls,
        content: type[Content],
        /,
        data: ScoredPoint,
    ) -> Self:
        if data.payload is None:
            raise ValueError("Missing qdrant data payload")

        identifier: UUID
        match data.id:
            case int() as int_id:
                identifier = UUID(int=int_id)

            case str() as str_id:
                identifier = UUID(hex=str_id)

        return cls(
            identifier=identifier,
            vector=_flat_vector(data.vector),
            score=data.score,
            content=content.from_mapping(data.payload),
        )


def _flat_vector(
    vector: Any,
    /,
) -> Mapping[str, Sequence[float]] | Sequence[float]:
    match vector:
        case {**vectors} if all(isinstance(item, float) for item in vectors.items()):
            return dict(vectors)

        case [*vector] if all(isinstance(element, float) for element in vector):
            return list(vector)

        case None:
            raise ValueError("Missing qdrant data vector")

        case _:
            raise ValueError("Unsupported qdrant data vector")


class QdrantPaginationToken(State):
    next_id: Any


class QdrantPaginationResult[Result](State):
    results: Sequence[Result]
    continuation_token: QdrantPaginationToken | None


@runtime_checkable
class QdrantCollectionCreating(Protocol):
    async def __call__[Model: DataModel](
        self,
        model: type[Model],
        /,
        *,
        vector_size: int,
        in_ram: bool,
        skip_existing: bool,
    ) -> bool: ...


@runtime_checkable
class QdrantCollectionIndexCreating(Protocol):
    async def __call__[Model: DataModel, Attribute](
        self,
        model: type[Model],
        /,
        *,
        path: AttributePath[Model, Attribute] | Attribute,
        index_type: Literal[
            "keyword",
            "integer",
            "float",
            "geo",
            "text",
            "bool",
            "datetime",
            "uuid",
        ],
    ) -> bool: ...


@runtime_checkable
class QdrantCollectionDeleting(Protocol):
    async def __call__[Model: DataModel](
        self,
        model: type[Model],
        /,
    ) -> None: ...


@runtime_checkable
class QdrantFetching(Protocol):
    async def __call__[Model: DataModel](
        self,
        model: type[Model],
        /,
        *,
        requirements: AttributeRequirement[Model] | None,
        continuation: QdrantPaginationToken | None,
        limit: int,
        return_vector: bool,
    ) -> QdrantPaginationResult[Embedded[Model]] | QdrantPaginationResult[Model]: ...


@runtime_checkable
class QdrantSearching(Protocol):
    async def __call__[Model: DataModel](  # noqa: PLR0913
        self,
        model: type[Model],
        /,
        *,
        query_vector: Sequence[float],
        requirements: AttributeRequirement[Model] | None,
        score_threshold: float | None,
        limit: int,
        return_vector: bool,
    ) -> Sequence[QdrantResult[Model]] | Sequence[Model]: ...


@runtime_checkable
class QdrantStoring(Protocol):
    async def __call__[Model: DataModel](
        self,
        model: type[Model],
        /,
        *,
        objects: Iterable[Embedded[Model]],
        batch_size: int,
        max_retries: int,
        parallel_tasks: int,
    ) -> None: ...


@runtime_checkable
class QdrantDeleting(Protocol):
    async def __call__[Model: DataModel](
        self,
        model: type[Model],
        /,
        *,
        requirements: AttributeRequirement[Model] | None,
    ) -> None: ...


class QdrantException(Exception):
    pass
