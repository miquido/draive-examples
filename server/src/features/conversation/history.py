from collections.abc import Generator, Sequence
from uuid import UUID

from draive import (
    ConversationMessage,
    ModelContext,
    ModelInput,
    ModelMemory,
    ModelMemoryRecall,
    ModelOutput,
)
from draive.postgres import PostgresModelMemory

__all__ = ("thread_history",)


async def thread_history(
    thread_id: UUID,
    *,
    limit: int,
) -> Sequence[ConversationMessage]:
    memory: ModelMemory = PostgresModelMemory(str(thread_id))
    recalled: ModelMemoryRecall = await memory.recall(limit=limit)

    return tuple(_message_from_context(recalled.context))


def _message_from_context(context: ModelContext) -> Generator[ConversationMessage]:
    for element in context:
        if element.contains_tools:
            continue  # skip tools messages

        if isinstance(element, ModelInput):
            yield ConversationMessage.user(element.content)

        else:
            assert isinstance(element, ModelOutput)  # nosec: B101
            yield ConversationMessage.model(element.content)
