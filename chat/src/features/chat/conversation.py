from collections.abc import AsyncIterator, Sequence
from datetime import datetime

from draive import (
    Conversation,
    ConversationMessage,
    ConversationOutputChunk,
    Toolbox,
)

__all__ = [
    "chat_stream",
]

INSTRUCTION: str = """\
You are helpful assistant.

Current time is {time}.
"""


async def chat_stream(
    message: ConversationMessage,
    memory: Sequence[ConversationMessage],
) -> AsyncIterator[ConversationOutputChunk]:
    return await Conversation.completion(
        instructions=INSTRUCTION.format(time=datetime.now().isoformat()),
        input=message,
        memory=memory,
        tools=Toolbox.empty,
        stream=True,
    )
