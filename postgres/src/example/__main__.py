from asyncio import run
from uuid import uuid4

from draive import Conversation, ConversationMessage, Instructions, ctx
from draive.openai import OpenAI, OpenAIChatConfig

from integrations.postgres import PostgresConnectionPool
from solutions.configuration import PostgresConfigurationProvider
from solutions.instructions import PostgresInstructionsRepository
from solutions.memory import PostgresConversationMemory


async def main() -> None:
    async with ctx.scope(
        "example",
        # declare postgres as configuration provider
        PostgresConfigurationProvider(),
        # declare postgres as instructons repository
        PostgresInstructionsRepository(),
        disposables=(
            OpenAI(),  # use OpenAI for LLM
            PostgresConnectionPool(),  # use postgres connection pool
        ),
    ):
        with ctx.updated(await OpenAIChatConfig.load()):
            result: ConversationMessage = await Conversation.completion(
                instruction=await Instructions.fetch("example"),
                input="Hello!",
                # declare postgres as conversation memory
                # use actual session ID to distinct multiple sessions
                memory=PostgresConversationMemory(session_id=uuid4()),
            )

            print(result)


run(main())
