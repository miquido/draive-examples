from draive import (
    ConversationMessage,
    ConversationResponseStream,
    Memory,
    MultimodalContent,
    Toolbox,
    conversation_completion,
)
from solutions.time import utc_datetime
from solutions.web import web_page_content

from features.knowledge import knowledge_search

__all__ = [
    "chat_respond",
]


async def chat_respond(
    instruction: str,
    message: MultimodalContent,
    memory: Memory[list[ConversationMessage], ConversationMessage],
) -> ConversationResponseStream:
    """
    Respond to chat conversation message using provided memory and instruction.
    """

    return await conversation_completion(
        instruction=instruction,  # pass the instruction
        input=message,  # use the input message
        memory=memory,  # work in context of given memory
        tools=Toolbox(  # allow using set of tools
            utc_datetime,
            web_page_content,
            knowledge_search,
            recursive_calls_limit=2,  # make sure it won't cause infinite loop
        ),
        stream=True,  # and use streaming api
    )
