from draive import (
    ConversationMessage,
    Memory,
    MultimodalContent,
    Toolbox,
    conversation_completion,
)

from features.news import prepare_news
from solutions.time import utc_datetime

__all__ = [
    "chat_respond",
]

INSTRUCTION: str = """\
You are a news agency employee working on a new news page according to provided requirements.

Guide the user through the process to gather all required information to prepare the news.
Ask for each missing information step by step and propose preparing news page when everything
is ready and the user agrees. News are always prepared by using "prepare_news" tool.

Use proposed websites and urls as sources for preparing news pages when requested.

Strictly focus on preparing the news and guide the user through that task. Try to go back on track
when user starts asking about anything not related to the task. When the news page is ready refuse
working further as your job is done.
"""


async def chat_respond(
    memory: Memory[list[ConversationMessage], ConversationMessage],
    message: MultimodalContent,
) -> ConversationMessage:
    """
    Respond to chat conversation message using provided memory and instruction.
    """

    return await conversation_completion(
        instruction=INSTRUCTION,
        input=message,
        memory=memory,
        tools=Toolbox(prepare_news, utc_datetime),
    )
