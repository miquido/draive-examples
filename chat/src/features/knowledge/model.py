from draive import DataModel

__all__ = [
    "KnowledgeItem",
]


class KnowledgeItem(DataModel):
    """
    Data model for storing knowledge in vector index
    """

    source: str
    content: str
