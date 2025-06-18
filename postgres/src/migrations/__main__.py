from asyncio import run

from draive import ctx, setup_logging

from integrations.postgres import PostgresConnectionPool
from migrations.postgres.execution import execute_postgres_migrations


async def migrate_databases() -> None:
    async with ctx.scope(
        "migrations",
        disposables=(PostgresConnectionPool(),),
    ):
        await execute_postgres_migrations()


def main() -> None:
    setup_logging("migrations")
    run(migrate_databases())


main()
