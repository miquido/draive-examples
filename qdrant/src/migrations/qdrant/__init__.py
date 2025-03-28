from migrations.qdrant.collections import setup_qdrant_collections

__all__ = [
    "perform_qdrant_setup",
]


async def perform_qdrant_setup() -> None:
    await setup_qdrant_collections()
