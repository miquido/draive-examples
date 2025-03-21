from collections.abc import AsyncIterator
from datetime import datetime

from draive import ConversationMessage, LMMStreamChunk, ProcessingEvent, conversation_completion

__all__ = [
    "chat_stream",
]

INSTRUCTION: str = """\
You are a company assistant helping employees in their daily job.

Current time is {time}.
"""


async def chat_stream(
    message: ConversationMessage,
) -> AsyncIterator[LMMStreamChunk | ProcessingEvent]:
    return await conversation_completion(
        instruction=INSTRUCTION.format(time=datetime.now().isoformat()),
        input=message,
        stream=True,
    )
