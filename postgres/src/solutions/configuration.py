import json
from collections.abc import Mapping

from draive import (
    BasicValue,
    Configuration,
    cache,
    ctx,
)

from integrations.postgres import Postgres
from integrations.postgres.types import PostgresRow

__all__ = ("PostgresConfigurationProvider",)


def PostgresConfigurationProvider() -> Configuration:
    @cache(expiration=60, limit=64)
    async def load(
        identifier: str,
    ) -> Mapping[str, BasicValue] | None:
        try:
            row: PostgresRow | None = await Postgres.fetch_one(
                LOAD_STATEMENT,
                identifier,
            )
            if row is None:
                return None

            return json.loads(row["content"])

        except Exception as exc:
            ctx.log_error(
                "Failed to load configuration from repository",
                exception=exc,
            )

            raise exc

    return Configuration(
        loading=load,
    )


LOAD_STATEMENT: str = """\
SELECT
    configurations.identifier,
    configurations.content

FROM
    configurations

WHERE
    configurations.identifier = $1

LIMIT
    1
;\
"""
