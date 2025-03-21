from asyncio import run

from draive import ctx, setup_logging

from integrations.postgres import PostgresClient
from migrations.postgres import perform_postgres_migrations


async def migrate_databases() -> None:
    async with ctx.scope(
        "migrations",
        disposables=[PostgresClient()],
    ):
        ctx.log_warning("Running postgres migrations, make sure it is not running on the server!")
        await perform_postgres_migrations()
        ctx.log_info("...postgres migrations completed")


def main() -> None:
    setup_logging("migrations")
    run(migrate_databases())


main()
