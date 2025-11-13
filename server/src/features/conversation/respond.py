from collections.abc import AsyncIterator
from uuid import UUID

from draive import (
    Conversation,
    ConversationOutputChunk,
    GuardrailsException,
    GuardrailsSafety,
    Multimodal,
    Template,
    ctx,
)
from draive.openai import OpenAIResponsesConfig
from draive.postgres import PostgresModelMemory

__all__ = ("thread_response_stream",)


async def thread_response_stream(
    thread_id: UUID,
    message: Multimodal,
) -> AsyncIterator[str]:
    try:
        async with ctx.scope(
            "thread_response_stream",
            await OpenAIResponsesConfig.load(
                identifier="conversation-response",
                required=True,
            ),
        ):
            async for chunk in await Conversation.completion(
                instructions=Template.of("conversation-response-instructions"),
                input=await GuardrailsSafety.sanitize(message),
                memory=PostgresModelMemory(str(thread_id)),
                stream=True,
            ):
                assert isinstance(chunk, ConversationOutputChunk)  # nosec: B101
                response_chunk: str = chunk.content.to_str().replace("\n", "\\n")
                yield f"event: response\ndata: {response_chunk}\n\n"

    except GuardrailsException as exc:
        yield "event: response\ndata: \\nResponse has been blocked due to safety reasons\n\n"
        ctx.log_error(
            "Response guardrails failure",
            exception=exc,
        )  # finish withouit exception - ends the stream

    except BaseException as exc:
        yield "event: exception\ndata: Unexpected error\n\n"
        ctx.log_error(
            "Response exception",
            exception=exc,
        )  # finish withouit exception - ends the stream
