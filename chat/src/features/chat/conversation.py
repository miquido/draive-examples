from collections.abc import AsyncIterator
from datetime import datetime

from draive import (
    Conversation,
    ConversationMemory,
    ConversationMessage,
    ConversationStreamElement,
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
    memory: ConversationMemory,
) -> AsyncIterator[ConversationStreamElement]:
    return await Conversation.completion(
        instruction=INSTRUCTION.format(time=datetime.now().isoformat()),
        input=message,
        memory=memory,
        tools=await Toolbox.fetched(),
        stream=True,
    )
