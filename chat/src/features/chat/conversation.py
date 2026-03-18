from collections.abc import Sequence
from datetime import datetime

from draive import (
    Conversation,
    ConversationOutputStream,
    ConversationTurn,
    MultimodalContent,
)

__all__ = [
    "chat_stream",
]

INSTRUCTION: str = """\
You are helpful assistant.

Current time is {time}.
"""


def chat_stream(
    message: MultimodalContent,
    memory: Sequence[ConversationTurn],
) -> ConversationOutputStream:
    return Conversation.completion(
        instructions=INSTRUCTION.format(time=datetime.now().isoformat()),
        message=message,
        memory=memory,
    )
