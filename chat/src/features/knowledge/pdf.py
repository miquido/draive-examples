from io import BytesIO

from draive import (
    VectorIndex,
    count_text_tokens,
    ctx,
    split_text,
)

from features.knowledge.model import KnowledgeItem
from integrations.pdf import read_pdf

__all__ = [
    "index_pdf",
]


async def index_pdf(
    source: BytesIO | str,
) -> None:
    """
    Add PDF from bytes or local path to the knowledge base
    using contextually provided VolatileVectorIndex.
    """

    ctx.log_debug("Indexing PDF %s", source)
    await ctx.state(VectorIndex).index(
        KnowledgeItem,
        indexed_value=KnowledgeItem._.content,
        values=[
            KnowledgeItem(
                source=source if isinstance(source, str) else "N/A",
                content=part,
            )
            for part in split_text(
                text=await read_pdf(source=source),
                part_size=256,
                part_overlap_size=32,
                count_size=count_text_tokens,
            )
        ],
    )
