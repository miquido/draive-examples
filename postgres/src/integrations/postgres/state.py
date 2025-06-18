from collections.abc import Iterable
from typing import Any

from draive import State, ctx

from integrations.postgres.types import (
    PostgresConnectionAcquiring,
    PostgresConnectionContext,
    PostgresRow,
    PostgresStatementExecuting,
    PostgresTransactionContext,
    PostgresTransactionPreparing,
)

__all__ = (
    "Postgres",
    "PostgresConnection",
)


class PostgresConnection(State):
    @classmethod
    async def fetch_one(
        cls,
        statement: str,
        /,
        *args: Any,
    ) -> PostgresRow | None:
        return next(
            (
                result
                for result in await ctx.state(cls).execute_statement(
                    statement,
                    *args,
                )
            ),
            None,
        )

    @classmethod
    async def fetch(
        cls,
        statement: str,
        /,
        *args: Any,
    ) -> Iterable[PostgresRow]:
        return await ctx.state(cls).execute_statement(
            statement,
            *args,
        )

    @classmethod
    async def execute(
        cls,
        statement: str,
        /,
        *args: Any,
    ) -> None:
        await ctx.state(cls).execute_statement(
            statement,
            *args,
        )

    @classmethod
    def transaction(cls) -> PostgresTransactionContext:
        return ctx.state(cls).prepare_transaction()

    execute_statement: PostgresStatementExecuting
    prepare_transaction: PostgresTransactionPreparing


class Postgres(State):
    @classmethod
    def acquire_connection(cls) -> PostgresConnectionContext:
        if ctx.check_state(PostgresConnection):
            raise RuntimeError("Recursive Postgres connection acquiring is forbidden")

        return ctx.state(cls).connection_acquiring()

    @classmethod
    async def fetch_one(
        cls,
        statement: str,
        /,
        *args: Any,
    ) -> PostgresRow | None:
        if ctx.check_state(PostgresConnection):
            return await PostgresConnection.fetch_one(statement, *args)

        async with ctx.disposables(cls.acquire_connection()):
            return await PostgresConnection.fetch_one(statement, *args)

    @classmethod
    async def fetch(
        cls,
        statement: str,
        /,
        *args: Any,
    ) -> Iterable[PostgresRow]:
        if ctx.check_state(PostgresConnection):
            return await PostgresConnection.fetch(statement, *args)

        async with ctx.disposables(cls.acquire_connection()):
            return await PostgresConnection.fetch(statement, *args)

    @classmethod
    async def execute(
        cls,
        statement: str,
        /,
        *args: Any,
    ) -> None:
        if ctx.check_state(PostgresConnection):
            return await PostgresConnection.execute(statement, *args)

        async with ctx.disposables(cls.acquire_connection()):
            return await PostgresConnection.execute(statement, *args)

    connection_acquiring: PostgresConnectionAcquiring
