from asyncio import run

from draive import ctx, setup_logging
from draive.postgres import Postgres, PostgresConnectionPool


async def migrate_databases() -> None:
    async with ctx.scope(
        "migrations",
        disposables=(PostgresConnectionPool(),),
    ):
        await Postgres.execute_migrations(f"{__package__}.postgres")


def main() -> None:
    setup_logging("migrations")
    run(migrate_databases())


main()
