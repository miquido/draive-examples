from commons.model import ExampleData
from integrations.qdrant import Qdrant

__all__ = [
    "setup_qdrant_collections",
]


async def setup_qdrant_collections() -> None:
    await Qdrant.create_collection(
        ExampleData,
        vector_size=1024,
        in_ram=True,
        skip_existing=True,
    )
