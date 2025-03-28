from collections.abc import Sequence

from draive import AttributeRequirement, DataModel, as_list
from qdrant_client.conversions.common_types import ScoredPoint

from integrations.qdrant.filters import prepare_filter
from integrations.qdrant.session import QdrantSession
from integrations.qdrant.types import QdrantResult

__all__ = [
    "QdrantSearchMixin",
]


class QdrantSearchMixin(QdrantSession):
    async def search[Model: DataModel](  # noqa: PLR0913
        self,
        model: type[Model],
        /,
        *,
        query_vector: Sequence[float],
        requirements: AttributeRequirement[Model] | None,
        score_threshold: float | None,
        limit: int,
        return_vector: bool,
    ) -> Sequence[QdrantResult[Model]] | Sequence[Model]:
        results: list[ScoredPoint] = await self._client.search(
            collection_name=model.__name__,
            query_filter=prepare_filter(
                requirements=requirements,
            ),
            query_vector=as_list(query_vector),
            score_threshold=score_threshold,
            limit=limit,
            with_payload=True,
            with_vectors=return_vector,
        )

        if return_vector:
            return tuple(
                QdrantResult[model].of(
                    model,
                    data=result,
                )
                for result in results
            )

        else:
            return tuple(
                model(**result.payload) for result in results if result.payload is not None
            )
