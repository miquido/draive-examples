from collections.abc import Sequence

from draive import (
    VectorIndex,
    ctx,
    tool,
)

from features.knowledge.model import KnowledgeItem

__all__ = [
    "knowledge_search",
]


@tool(name="search", description="Search conversation attachments and documents")
async def knowledge_search(query: str) -> str:
    """
    Search the knowledge base using contextually provided VolatileVectorIndex.
    """

    results: Sequence[KnowledgeItem] = await ctx.state(VectorIndex).search(
        KnowledgeItem,
        query=query,
        limit=3,
    )

    return "\n---\n".join(
        [f"source:\n{result.source}\ncontent:\n{result.content}" for result in results]
    )
