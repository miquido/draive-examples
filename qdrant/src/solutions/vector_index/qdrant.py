from collections.abc import Callable, Iterable, Sequence
from typing import Any, cast

from draive import (
    AttributePath,
    AttributeRequirement,
    DataModel,
    Embedded,
    MediaContent,
    TextContent,
    VectorIndex,
    embed_image,
    embed_images,
    embed_text,
    embed_texts,
    mmr_vector_similarity_search,
)

from integrations.qdrant import Qdrant

__all__ = [
    "QdrantVectorIndex",
]


def QdrantVectorIndex() -> VectorIndex:  # noqa: C901, PLR0915
    async def index[Model: DataModel, Value: MediaContent | TextContent | str](
        model: type[Model],
        /,
        values: Iterable[Model],
        attribute: Callable[[Model], Value] | AttributePath[Model, Value] | Value,
        **extra: Any,
    ) -> None:
        value_selector: Callable[[Model], Value]
        match attribute:
            case Callable() as selector:
                value_selector = selector

            case path:
                assert isinstance(  # nosec: B101
                    path, AttributePath
                ), "Prepare parameter path by using Self._.path.to.property"
                value_selector = cast(AttributePath[Model, Value], path).__call__

        selected_values: list[str | bytes] = []
        for value in values:
            match value_selector(value):
                case str() as text:
                    selected_values.append(text)

                case TextContent() as text_content:
                    selected_values.append(text_content.text)

                case MediaContent() as media_content:
                    if media_content.kind != "image":
                        raise ValueError(f"{media_content.kind} embedding is not supported")

                    if not isinstance(media_content.source, bytes):
                        raise ValueError("Media references are not supported")

                    selected_values.append(media_content.source)

        embedded_values: Sequence[Embedded[str] | Embedded[bytes]]
        if all(isinstance(value, str) for value in selected_values):
            embedded_values = await embed_texts(
                cast(list[str], selected_values),
                **extra,
            )

        elif all(value for value in selected_values):
            embedded_values = await embed_images(
                cast(list[bytes], selected_values),
                **extra,
            )

        else:
            raise ValueError("Selected attribute values have to be the same type")

        await Qdrant.store(
            model,
            objects=[
                Embedded(
                    value=value,
                    vector=embedded.vector,
                )
                for value, embedded in zip(
                    values,
                    embedded_values,
                    strict=True,
                )
            ],
        )

    async def search[Model: DataModel](  # noqa: PLR0913
        model: type[Model],
        /,
        query: Sequence[float] | MediaContent | TextContent | str | None = None,
        score_threshold: float | None = None,
        requirements: AttributeRequirement[Model] | None = None,
        limit: int | None = None,
        rerank: bool = False,
        **extra: Any,
    ) -> Iterable[Model]:
        assert query is not None or (query is None and score_threshold is None)  # nosec: B101
        query_vector: Sequence[float]
        match query:
            case None:
                results = await Qdrant.fetch(
                    model,
                    requirements=requirements,
                    limit=limit or 8,
                )
                return results.results

            case str() as text:
                embedded_query: Embedded[str] = await embed_text(text)
                query_vector = embedded_query.vector

            case TextContent() as text_content:
                embedded_query: Embedded[str] = await embed_text(text_content.text)
                query_vector = embedded_query.vector

            case MediaContent() as media_content:
                if media_content.kind != "image":
                    raise ValueError(f"{media_content.kind} embedding is not supported")

                if not isinstance(media_content.source, bytes):
                    raise ValueError("Media references are not supported")

                embedded_image: Embedded[bytes] = await embed_image(
                    media_content.source,
                    **extra,
                )
                query_vector = embedded_image.vector

            case vector:
                query_vector = vector

        matching: Sequence[Embedded[Model]] = [
            Embedded(
                value=result.content,
                vector=cast(Sequence[float], result.vector),
            )
            for result in await Qdrant.search(
                model,
                query_vector=query_vector,
                requirements=requirements,
                score_threshold=score_threshold,
                limit=limit or 8,
                return_vector=True,
            )
        ]

        if not rerank:
            return [element.value for element in matching]

        return [
            matching[index].value
            for index in mmr_vector_similarity_search(
                query_vector=query_vector,
                values_vectors=[element.vector for element in matching],
                limit=limit,
            )
        ]

    async def delete[Model: DataModel](
        model: type[Model],
        /,
        *,
        requirements: AttributeRequirement[Model] | None = None,
        **extra: Any,
    ) -> None:
        await Qdrant.delete(
            model,
            requirements=requirements,
        )

    return VectorIndex(
        indexing=index,
        searching=search,
        deleting=delete,
    )
