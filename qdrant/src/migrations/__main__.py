from asyncio import run

from draive import ctx, setup_logging

from integrations.qdrant import QdrantClient
from migrations.qdrant import perform_qdrant_setup


async def migrate_databases() -> None:
    async with ctx.scope(
        "migrations",
        disposables=[
            QdrantClient(),
        ],
    ):
        ctx.log_info("Running Qdrant setup...")
        await perform_qdrant_setup()
        ctx.log_info("...Qdrant setup completed")


def main() -> None:
    setup_logging("migrations")
    run(migrate_databases())


main()
