from asyncio import run

from draive import ctx, setup_logging
from draive.postgres import Postgres, PostgresConnectionPool


async def migrate_databases() -> None:
    async with ctx.scope("migrations", disposables=(PostgresConnectionPool(),)):
        ctx.log_warning("Running postgres migrations...")
        await Postgres.execute_migrations("migrations.postgres")
        ctx.log_info("...postgres migrations completed")


def main() -> None:
    setup_logging("migrations")
    run(migrate_databases())


main()
