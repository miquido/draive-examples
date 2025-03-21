import os
import pkgutil
from collections.abc import Sequence
from importlib import import_module

from draive import ctx

from integrations.postgres import Postgres, PostgresRow
from migrations.postgres.base import BaseMigration

__all__ = [
    "perform_postgres_migrations",
]

# auto load all Migration classes from all files starting with "migration_" and sort by number
MIGRATIONS: list[BaseMigration] = [
    import_module(name=f"migrations.postgres.{name}").Migration(number=number)
    for name, number in sorted(
        [
            (module, int(module[len("migration_") :]))
            for _, module, _ in pkgutil.iter_modules([os.path.dirname(__file__)])
            if module.startswith("migration_")
        ],
        key=lambda element: element[1],
    )
]


async def perform_postgres_migrations() -> None:
    async with ctx.state(Postgres).connection() as connection:
        # make sure migrations table exists
        await connection.execute(
            """
                CREATE TABLE IF NOT EXISTS migrations (
                    id SERIAL PRIMARY KEY,
                    executed_at TIMESTAMP NOT NULL DEFAULT NOW()
                );
                """
        )
        # get current version
        fetched_version: Sequence[PostgresRow] = await connection.execute(
            """
                SELECT COUNT(*) as count FROM migrations;
                """
        )
        current_version: int
        if fetched_version:
            current_version = int(fetched_version[0].get("count", 0))

        else:
            current_version = 0

        ctx.log_info(f"Current database version: {current_version}")

        # perform migrations from current version to latest
        for migration in MIGRATIONS[current_version:]:
            await migration(
                connection=connection,
            )
