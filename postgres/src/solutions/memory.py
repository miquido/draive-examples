import json
from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from draive import (
    ConversationElement,
    ConversationMemory,
    ConversationMessage,
    ctx,
)

from integrations.postgres import Postgres, PostgresConnection

__all__ = ("PostgresConversationMemory",)


def PostgresConversationMemory(
    *,
    session_id: UUID,
    message_recall_limit: int = 16,
) -> ConversationMemory:
    async def recall(
        **extra: Any,
    ) -> Sequence[ConversationMessage]:
        try:
            return tuple(
                reversed(
                    [
                        _decode_message(record)
                        for record in await Postgres.fetch(
                            RECALL_STATEMENT,
                            session_id,
                            message_recall_limit,
                        )
                    ]
                )
            )

        except Exception as exc:
            ctx.log_error(
                "Failed to retrieve conversation messages from memory",
                exception=exc,
            )

            raise exc

    async def remember(
        *items: ConversationElement,
        **extra: Any,
    ) -> None:
        async with ctx.disposables(Postgres.acquire_connection()):
            async with PostgresConnection.transaction():
                for message in items:
                    if not isinstance(message, ConversationMessage):
                        continue  # skip events

                    await PostgresConnection.execute(
                        REMEMBER_STATEMENT,
                        session_id,
                        message.created,
                        message.role,
                        message.content.to_json(),
                        message.meta.to_json(),
                    )

    return ConversationMemory(
        recall=recall,
        remember=remember,
    )


def _decode_message(
    record: Mapping[str, Any],
) -> ConversationMessage:
    return ConversationMessage(
        identifier=record["identifier"],
        created=record["created"],
        role=record["role"],
        content=json.loads(record["content"]),
        meta=json.loads(record["meta"]),
    )


RECALL_STATEMENT: str = """
SELECT
    conversation_messages.id as identifier,
    conversation_messages.created AS created,
    conversation_messages.role AS role,
    conversation_messages.content AS content,
    conversation_messages.meta AS meta

FROM
    conversation_messages

WHERE
    conversation_messages.session_id = $1

ORDER BY
    conversation_messages.created DESC

LIMIT
    $2
;
"""

REMEMBER_STATEMENT: str = """
INSERT INTO
    conversation_messages (
        session_id,
        created,
        role,
        content,
        meta
    )
VALUES (
    $1,
    $2,
    $3,
    $4,
    $5
);
"""
