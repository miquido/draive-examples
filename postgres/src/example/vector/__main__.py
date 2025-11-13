from asyncio import run
from uuid import UUID, uuid4

from asyncpg.connection import Connection
from draive import DataModel, Default, ctx
from draive.openai import OpenAI
from draive.postgres import PostgresConnectionPool, PostgresVectorIndex
from draive.utils import VectorIndex
from pgvector.asyncpg import register_vector  # pyright: ignore


# Inline model definition
class Chunk(DataModel):
    identifier: UUID = Default(default_factory=uuid4)
    text: str


# Inline pgvector initialization
async def initialize_pgvector(connection: Connection) -> None:
    await register_vector(connection)


async def main() -> None:
    async with ctx.scope(
        "vector_example",
        PostgresVectorIndex(),
        disposables=(
            OpenAI(),  # Use OpenAI for embeddings
            PostgresConnectionPool(
                initialize=initialize_pgvector
            ),  # Postgres with pgvector support
        ),
    ):
        # Step 1: Create and index sample chunks
        chunks = [
            Chunk(text="Python is a high-level programming language"),
            Chunk(text="PostgreSQL is a powerful relational database"),
            Chunk(text="Machine learning is a subset of artificial intelligence"),
            Chunk(text="Docker is a containerization platform"),
            Chunk(text="FastAPI is a modern Python web framework"),
            Chunk(text="Kubernetes orchestrates containerized applications"),
            Chunk(text="GraphQL is a query language for APIs"),
            Chunk(text="Redis is an in-memory data structure store"),
            Chunk(text="Terraform enables infrastructure as code"),
            Chunk(text="Nginx is a high-performance web server"),
        ]

        ctx.log_info(f"Indexing {len(chunks)} chunks...")
        await VectorIndex.index(
            Chunk,
            values=chunks,
            attribute=Chunk._.text,
        )
        ctx.log_info("Indexing complete!")

        # Step 2: Search for similar content
        query = "What is Python?"
        ctx.log_info(f"Searching for: '{query}'")

        results = await VectorIndex.search(
            Chunk,
            query=query,
            limit=3,
            score_threshold=0.0,
            rerank=False,
        )

        ctx.log_info(f"Found {len(results)} results:")
        for idx, result in enumerate(results, 1):
            ctx.log_info(f"  {idx}. {result.text}")

        # Step 3: Clean up indexed data
        ctx.log_info("Cleaning up indexed data...")
        await VectorIndex.delete(Chunk)
        ctx.log_info("Cleanup complete!")


if __name__ == "__main__":
    run(main())
