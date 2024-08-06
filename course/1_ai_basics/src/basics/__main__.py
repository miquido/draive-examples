from asyncio import run

from draive import LMM, ctx, generate_text, load_env, setup_logging
from draive.openai import OpenAIChatConfig, OpenAIClient, openai_lmm_invocation

load_env()

setup_logging()


async def main() -> None:
    async with ctx.new(
        dependencies=[OpenAIClient],
        state=[
            OpenAIChatConfig(model="gpt-3.5-turbo"),
            LMM(invocation=openai_lmm_invocation),
        ],
    ):
        result: str = await generate_text(
            instruction="You are a helpful assistant",
            input="Hello!",
        )
        print(result)


run(main())
