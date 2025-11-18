from collections.abc import Mapping
from uuid import UUID, uuid4

from draive import BasicValue, ModelMemory
from draive.postgres import PostgresModelMemory

__all__ = ("thread_prepare",)


async def thread_prepare(
    variables: Mapping[str, BasicValue] | None = None,
) -> UUID:
    thread_id: UUID = uuid4()
    memory: ModelMemory = PostgresModelMemory(thread_id)
    await memory.maintenance(variables=variables)
    return thread_id
