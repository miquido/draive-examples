from uuid import UUID

from draive import ConversationTurn, Paginated, Pagination
from draive.postgres import PostgresConversationMemory

__all__ = ("thread_history",)


async def thread_history(
    thread: UUID | str,
    pagination: Pagination,
) -> Paginated[ConversationTurn]:
    return await PostgresConversationMemory(thread=thread).fetch(
        pagination=pagination,
    )
