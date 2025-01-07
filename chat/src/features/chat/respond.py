from collections.abc import AsyncIterator, Sequence
from typing import Literal, overload

from draive import (
    ConversationMessage,
    LMMStreamChunk,
    Memory,
    MultimodalContent,
    conversation_completion,
)

from features.knowledge import knowledge_search
from solutions.time import utc_datetime
from solutions.web import web_page_content

__all__ = [
    "chat_respond",
]


@overload
async def chat_respond(
    instruction: str,
    message: MultimodalContent,
    memory: Memory[Sequence[ConversationMessage], ConversationMessage],
    stream: Literal[False] = False,
) -> ConversationMessage: ...


@overload
async def chat_respond(
    instruction: str,
    message: MultimodalContent,
    memory: Memory[Sequence[ConversationMessage], ConversationMessage],
    stream: Literal[True],
) -> AsyncIterator[LMMStreamChunk]: ...


async def chat_respond(
    instruction: str,
    message: MultimodalContent,
    memory: Memory[Sequence[ConversationMessage], ConversationMessage],
    stream: bool = False,
) -> AsyncIterator[LMMStreamChunk] | ConversationMessage:
    """
    Respond to chat conversation message using provided memory and instruction.
    """

    if stream:
        return await conversation_completion(
            instruction=instruction,  # pass the instruction
            input=message,  # use the input message
            memory=memory,  # work in context of given memory
            tools=[  # allow using set of tools
                utc_datetime,
                web_page_content,
                knowledge_search,
            ],
            stream=True,  # and use streaming api
        )

    else:
        return await conversation_completion(
            instruction=instruction,  # pass the instruction
            input=message,  # use the input message
            memory=memory,  # work in context of given memory
            tools=[  # allow using set of tools
                utc_datetime,
                web_page_content,
                knowledge_search,
            ],
        )
