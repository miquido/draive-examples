from abc import ABC, abstractmethod

from draive import ctx

from integrations.postgres import PostgresConnection

__all__ = [
    "BaseMigration",
]


class BaseMigration(ABC):
    def __init__(
        self,
        number: int,
    ) -> None:
        self._number: int = number

    @abstractmethod
    async def execute(
        self,
        *,
        connection: PostgresConnection,
    ): ...

    async def __call__(
        self,
        *,
        connection: PostgresConnection,
    ) -> None:
        with ctx.scope(self.__class__.__name__):
            ctx.log_info(f"Executing migration {self._number}")
            try:
                async with connection.transaction():
                    await self.execute(connection=connection)

                    # bump version by adding a row to migrations table
                    await connection.execute(
                        """
                        INSERT INTO migrations DEFAULT VALUES;
                        """
                    )

            except Exception as exc:
                ctx.log_info(f"Migration {self._number} failed")
                raise exc

            else:
                ctx.log_info(f"Migration {self._number} completed")
