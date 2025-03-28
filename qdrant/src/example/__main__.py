from asyncio import run
from collections.abc import Iterable

from draive import VectorIndex, ctx
from draive.cohere import Cohere, CohereTextEmbeddingConfig

from commons.model import ExampleData
from integrations.qdrant import QdrantClient
from solutions.vector_index import QdrantVectorIndex


async def main() -> None:
    cohere = Cohere()
    async with ctx.scope(
        "example",
        QdrantVectorIndex(),
        CohereTextEmbeddingConfig(
            model="embed-multilingual-v3.0",
            purpose="search_document",
        ),
        cohere.text_embedding(),
        disposables=(
            cohere,
            QdrantClient(),
        ),
    ):
        # index data
        await VectorIndex.index(
            ExampleData,
            attribute=ExampleData._.value,
            values=(
                ExampleData(value="lorem ipsum"),
                ExampleData(value="dolor sit amet"),
            ),
        )

        # search matching
        result: Iterable[ExampleData] = await VectorIndex.search(
            ExampleData,
            query="lorem amet",
            limit=1,
        )

        print(result)


run(main())
