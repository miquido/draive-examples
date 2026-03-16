from collections.abc import AsyncIterator
from uuid import UUID

from draive import (
    Conversation,
    ConversationEvent,
    GuardrailsException,
    GuardrailsSafety,
    ModelReasoningChunk,
    Multimodal,
    Template,
    ctx,
)
from draive.openai import OpenAIResponsesConfig
from draive.postgres import PostgresConversationMemory

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
            async for chunk in Conversation.completion(
                instructions=Template.of("conversation-response-instructions"),
                memory=PostgresConversationMemory(thread=thread_id),
                message=await GuardrailsSafety.sanitize(message),
            ):
                if isinstance(chunk, ConversationEvent):
                    response_chunk: str = (
                        chunk.content.to_str() if chunk.content is not None else "N/A"
                    )
                    yield f"event: event\ndata: {response_chunk}\n\n"

                elif isinstance(chunk, ModelReasoningChunk):
                    response_chunk: str = chunk.reasoning_chunk.to_str()
                    yield f"event: reasoning\ndata: {response_chunk}\n\n"

                else:
                    response_chunk: str = chunk.to_str()
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
