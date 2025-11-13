from asyncio import run

from draive import TextEmbedding, ctx, setup_logging

from integrations.onnx import ONNXEmbeddingModel

setup_logging("embedding")


async def embedding() -> None:
    async with ctx.scope(
        "embedding",
        disposables=(
            ONNXEmbeddingModel(
                "./models/embedding/model.onnx",
                execution_provider="CPUExecutionProvider",
            ),
        ),
    ):
        embedded = await TextEmbedding.embed_many(
            (
                "Lorem ipsum dolor sit amet",
                "More things to embed",
                "Using locally running model",
            )
        )

        print(embedded)


run(embedding())
