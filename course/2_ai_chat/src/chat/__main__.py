from bs4 import BeautifulSoup
from chainlit import Message, on_chat_start, on_message, user_session  # type: ignore
from draive import (
    LMM,
    ConversationMessage,
    VolatileAccumulativeMemory,
    conversation_completion,
    ctx,
    load_env,
    setup_logging,
    tool,
)
from draive.openai import OpenAIChatConfig, OpenAIClient, openai_lmm_invocation
from httpx import AsyncClient, Response

load_env()

setup_logging()


@tool
async def website_content(url: str) -> str:
    async with AsyncClient(follow_redirects=True) as client:
        response: Response = await client.get(url)
        content: bytes = await response.aread()
        page = BeautifulSoup(
            markup=content,
            features="html.parser",
        )
        return (page.find(name="main") or page.find(name="body") or page).text


@on_chat_start
async def setup() -> None:
    user_session.set("memory", VolatileAccumulativeMemory[ConversationMessage]())  # type: ignore


@on_message
async def respond(
    message: Message,
) -> None:
    async with ctx.new(
        dependencies=[OpenAIClient],
        state=[
            OpenAIChatConfig(model="gpt-3.5-turbo"),
            LMM(invocation=openai_lmm_invocation),
        ],
    ):
        result: ConversationMessage = await conversation_completion(
            instruction="You are a helpful assistant",
            input=message.content,
            memory=user_session.get("memory"),  # type: ignore
            tools=[website_content],
        )

        response: Message = Message(
            author="assistant",
            content=result.content.as_string(),
        )
        await response.send()
