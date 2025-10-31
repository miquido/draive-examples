from asyncio import run

from draive import (
    Conversation,
    ConversationMessage,
    Template,
    ctx,
)
from draive.openai import OpenAI, OpenAIResponsesConfig
from draive.postgres import (
    PostgresConfigurationRepository,
    PostgresConnectionPool,
    PostgresModelMemory,
    PostgresTemplatesRepository,
)


async def main() -> None:
    async with ctx.scope(
        "example",
        # declare postgres as configuration provider
        PostgresConfigurationRepository(),
        # declare postgres as templates repository
        PostgresTemplatesRepository(),
        disposables=(
            OpenAI(),  # use OpenAI for LLM
            PostgresConnectionPool(),  # use postgres connection pool
        ),
    ):
        with ctx.updated(await OpenAIResponsesConfig.load()):
            memory = PostgresModelMemory("example_session")
            await memory.maintenance()  # initialize session if needed
            result: ConversationMessage = await Conversation.completion(
                instructions=Template.of("example"),
                input="Hello!",
                # declare postgres as conversation memory
                # use actual session ID to distinct multiple sessions
                memory=memory,
            )

            print(result)


run(main())
