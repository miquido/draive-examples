from draive import getenv_int, getenv_str

__all__ = [
    "QDRANT_HOST",
    "QDRANT_PORT",
]

QDRANT_HOST: str = getenv_str("QDRANT_HOST", default="localhost")
QDRANT_PORT: int = getenv_int("QDRANT_PORT", default=6334)
