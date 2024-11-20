from asyncio import get_running_loop
from base64 import b64encode
from collections.abc import AsyncIterator
from typing import Any, cast

from chainlit import (
    Audio,
    ChatProfile,
    ChatSettings,
    Component,
    ErrorMessage,
    File,
    Image,
    Message,
    Pdf,
    Starter,
    Text,
    Video,
    on_chat_start,  # type: ignore
    on_message,  # type: ignore
    on_settings_update,  # type: ignore
    set_chat_profiles,  # type: ignore
    set_starters,  # type: ignore
    user_session,
)
from chainlit.input_widget import TextInput
from draive import (
    ConversationMessage,
    DataModel,
    LMMStreamChunk,
    MediaContent,
    MultimodalContent,
    State,
    TextContent,
    VolatileAccumulativeMemory,
    VolatileVectorIndex,
    ctx,
    load_env,
    setup_logging,
    usage_metrics_logger,
)
from draive.anthropic import (
    AnthropicConfig,
    anthropic_lmm,
    anthropic_tokenizer,
)
from draive.fastembed import fastembed_text_embedding
from draive.gemini import (
    GeminiConfig,
    gemini_lmm,
    gemini_text_embedding,
    gemini_tokenizer,
)
from draive.ollama import OllamaChatConfig, ollama_lmm
from draive.openai import (
    OpenAIChatConfig,
    openai_lmm,
    openai_streaming_lmm,
    openai_text_embedding,
    openai_tokenizer,
)

from features.chat import chat_respond
from features.knowledge import index_pdf
from integrations.websites import WebsiteClient

load_env()  # load env first if needed
setup_logging("demo", "metrics")

DEFAULT_TEMPERATURE: float = 0.75
DEFAULT_PROMPT: str = """\
You are a helpful assistant.

You can access conversation documents by using "search" tool when user refers to the documents send.
Prefer getting knowledge from those if able.
"""


@set_chat_profiles
async def prepare_profiles(user: Any) -> list[ChatProfile]:
    """
    Prepare chat profiles allowing to select service providers
    """

    return [
        ChatProfile(
            name="gpt-4o-mini",
            markdown_description="**GPT-4o-mini**\nMultimodal with tools",
            default=True,
        ),
        ChatProfile(
            name="gpt-4o",
            markdown_description="**GPT-4o**\nMultimodal with tools",
            default=False,
        ),
        ChatProfile(
            name="gemini-1.5-flash",
            markdown_description="**Gemini-Flash**\nMultimodal with tools",
            default=False,
        ),
        ChatProfile(
            name="claude-sonnet-3.5",
            markdown_description="**sonnet-3.5**\nMultimodal with tools",
            default=False,
        ),
        ChatProfile(
            name="llama3:8B",
            markdown_description="**LLama3**\nText only without tools, accessed through Ollama.",
            default=False,
        ),
    ]


@set_starters
async def prepare_starters(user: Any) -> list[Starter]:
    """
    List of starter messages for the chat, can be used for a common task shortcuts
    or as a showcase of the implemented features.
    """

    return [
        Starter(
            label="Explain superconductors",
            message="Explain superconductors like I'm five years old.",
        ),
        Starter(
            label="Python script for daily email reports",
            message="Write a script to automate sending daily email reports in Python,"
            " and walk me through how I would set it up.",
        ),
    ]


@on_chat_start
async def prepare() -> None:
    """
    Prepare chat session which includes preparing a set of dependencies
    matching selected profile (services provider) and settings.
    """

    # prepare chat session memory - we are using volatile memory
    # which will return up to 8 last messages to the LLM context
    user_session.set(  # pyright: ignore[reportUnknownMemberType]
        "chat_memory",
        VolatileAccumulativeMemory[ConversationMessage]([], limit=8),
    )
    # select services based on current profile and form a base state for session
    state: list[State] = [
        VolatileVectorIndex(storage={}),  # it will be used as a knowledge base
        await WebsiteClient.prepare().initialize(),
    ]
    match user_session.get("chat_profile"):  # pyright: ignore[reportUnknownMemberType]
        case "gpt-4o-mini":
            user_session.set(  # pyright: ignore[reportUnknownMemberType]
                "streaming",
                True,
            )
            state.extend(
                [
                    openai_lmm(),
                    openai_streaming_lmm(),
                    openai_tokenizer("gpt-4o-mini"),
                    openai_text_embedding(),
                    OpenAIChatConfig(
                        model="gpt-4o-mini",
                        temperature=DEFAULT_TEMPERATURE,
                    ),
                ]
            )

        case "gpt-4o":
            user_session.set(  # pyright: ignore[reportUnknownMemberType]
                "streaming",
                True,
            )
            state.extend(
                [
                    openai_lmm(),
                    openai_streaming_lmm(),
                    openai_tokenizer("gpt-4o"),
                    openai_text_embedding(),
                    OpenAIChatConfig(
                        model="gpt-4o",
                        temperature=DEFAULT_TEMPERATURE,
                    ),
                ]
            )

        case "llama3:8B":
            user_session.set(  # pyright: ignore[reportUnknownMemberType]
                "streaming",
                False,
            )
            state.extend(
                [
                    ollama_lmm(),
                    # TODO: use actual llama tokenizer
                    # using OpenAI config to select tokenizer
                    openai_tokenizer("gpt-4o-mini"),
                    # use locally running embedding
                    await fastembed_text_embedding("nomic-ai/nomic-embed-text-v1.5"),
                    OllamaChatConfig(
                        model="llama3:8B",
                        temperature=DEFAULT_TEMPERATURE,
                    ),
                ]
            )

        case "gemini-1.5-flash":
            user_session.set(  # pyright: ignore[reportUnknownMemberType]
                "streaming",
                False,
            )
            state.extend(
                [
                    gemini_lmm(),
                    gemini_tokenizer("gemini-1.5-flash"),
                    gemini_text_embedding(),
                    GeminiConfig(
                        model="gemini-1.5-flash",
                        temperature=DEFAULT_TEMPERATURE,
                    ),
                ]
            )

        case "claude-sonnet-3.5":
            user_session.set(  # pyright: ignore[reportUnknownMemberType]
                "streaming",
                False,
            )
            state.extend(
                [
                    anthropic_lmm(),
                    anthropic_tokenizer(),
                    # use locally running embedding
                    await fastembed_text_embedding("nomic-ai/nomic-embed-text-v1.5"),
                    AnthropicConfig(
                        model="claude-3-5-sonnet-20240620",
                        temperature=DEFAULT_TEMPERATURE,
                    ),
                ]
            )

        case other:  # pyright: ignore[reportUnknownVariableType]
            raise RuntimeError("Invalid profile %s", other)  # type: ignore

    # use selected services by setting up session state
    user_session.set(  # pyright: ignore[reportUnknownMemberType]
        "state",
        state,
    )

    # prepare system prompt
    user_session.set(  # pyright: ignore[reportUnknownMemberType]
        "system_prompt",
        DEFAULT_PROMPT,
    )

    # prepare available settings
    await ChatSettings(
        [
            TextInput(
                id="system_prompt",
                label="System prompt",
                initial=DEFAULT_PROMPT,
                multiline=True,
            ),
        ]
    ).send()


@on_settings_update
async def update_settings(settings: dict[str, Any]) -> None:
    user_session.set(  # pyright: ignore[reportUnknownMemberType]
        "system_prompt",
        settings.get("system_prompt", DEFAULT_PROMPT),
    )


@on_message
async def message(
    message: Message,
) -> None:
    """
    Handle incoming message and stream the response
    """

    # enter a new context for processing each message
    # using session state and shared dependencies
    async with ctx.scope(
        "chat",
        *user_session.get("state", []),  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType, reportArgumentType]
        completion=usage_metrics_logger(),
    ):
        if user_session.get("streaming", False):  # pyright: ignore[reportUnknownMemberType, reportArgumentType]
            response_message: Message = Message(author="assistant", content="")
            await response_message.send()  # prepare message for streaming
            try:
                # request a chat conversation completion stream
                response_stream: AsyncIterator[LMMStreamChunk] = await chat_respond(  # pyright: ignore[reportCallIssue, reportUnknownVariableType]
                    instruction=user_session.get("system_prompt", DEFAULT_PROMPT),  # pyright: ignore[reportUnknownMemberType, reportArgumentType]
                    # convert message from chainlit to draive
                    message=await _as_multimodal_content(
                        content=message.content,
                        elements=message.elements,  # pyright: ignore[reportArgumentType]
                    ),
                    memory=user_session.get("chat_memory"),  # pyright: ignore[reportUnknownMemberType, reportArgumentType]
                    stream=True,
                )

                async for chunk in response_stream:  # pyright: ignore[reportUnknownVariableType]
                    for element in _as_message_content(chunk.content):  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType]
                        match element:
                            case Text() as text:
                                # for a text message part simply add it to the UI
                                # this might not be fully accurate but chainlit seems to
                                # not support it any other way (except custom implementation)
                                await response_message.stream_token(str(text.content))

                            case other:
                                # for a media add it separately
                                response_message.elements.append(other)  # pyright: ignore[reportArgumentType]
                                await response_message.update()

            except Exception as exc:
                ctx.log_error("Conversation failed", exception=exc)
                # replace the message with the error message as the result
                # not the best error handling but still handling
                await response_message.remove()
                await ErrorMessage(content=str(exc)).send()

            else:
                await response_message.update()  # finalize the message

        else:
            try:
                response = await chat_respond(
                    instruction=user_session.get("system_prompt", DEFAULT_PROMPT),  # pyright: ignore[reportUnknownMemberType, reportArgumentType]
                    # convert message from chainlit to draive
                    message=await _as_multimodal_content(
                        content=message.content,
                        elements=message.elements,  # pyright: ignore[reportArgumentType]
                    ),
                    memory=user_session.get("chat_memory"),  # pyright: ignore[reportUnknownMemberType, reportArgumentType]
                )

                await Message(author="assistant", content=response.content.as_string()).send()

            except Exception as exc:
                ctx.log_error("Conversation failed", exception=exc)
                await ErrorMessage(content=str(exc)).send()


# helper method for loading data from file
def _load_file_content(path: str) -> bytes:
    with open(path, "rb") as file:
        return file.read()


# async wrapper for the helper method above
async def _load_file_bytes(path: str) -> bytes:
    return await get_running_loop().run_in_executor(
        None,
        _load_file_content,
        path,
    )


# helper for getting base64 data from the local file
async def _load_file_b64(path: str) -> str:
    file_content: bytes = await _load_file_bytes(path)
    return b64encode(file_content).decode("utf-8")


async def _as_multimodal_content(  # noqa: C901, PLR0912
    content: str,
    elements: list[Text | Image | Audio | Video | Pdf | File],
) -> MultimodalContent:
    """
    Convert message content parts from chainlit to draive.
    """

    parts: list[Any] = [content]
    for element in elements:
        match element:
            case Text() as text:
                parts.append(text.content)

            case Image() as image:
                if url := image.url:
                    parts.append(
                        MediaContent.url(
                            url,
                            media="image",
                        )
                    )

                elif path := image.path:
                    parts.append(
                        MediaContent.base64(
                            await _load_file_b64(path),
                            media=cast(
                                Any,
                                image.mime or "image/jpeg",
                            ),
                        )
                    )

                else:
                    raise NotImplementedError("Unsupported image content")

            case Audio() as audio:
                if url := audio.url:
                    parts.append(
                        MediaContent.url(
                            url,
                            media="audio",
                        )
                    )

                elif path := audio.path:
                    parts.append(
                        MediaContent.base64(
                            await _load_file_b64(path),
                            media=cast(
                                Any,
                                audio.mime or "audio/wav",
                            ),
                        )
                    )

                else:
                    raise NotImplementedError("Unsupported audio content")

            case Video() as video:
                if url := video.url:
                    parts.append(
                        MediaContent.url(
                            url,
                            media="video",
                        )
                    )

                elif path := video.path:
                    parts.append(
                        MediaContent.base64(
                            await _load_file_b64(path),
                            media=cast(
                                Any,
                                video.mime or "video/mpeg",
                            ),
                        )
                    )

                else:
                    raise NotImplementedError("Unsupported video content")

            case Pdf() as pdf:
                if path := pdf.path:
                    await index_pdf(source=path)

                else:
                    raise NotImplementedError("Unsupported pdf content")

            case File() as file:
                if path := file.path:
                    if path.endswith(".pdf"):
                        await index_pdf(source=path)

                    elif path.endswith(".mp3"):
                        parts.append(
                            MediaContent.base64(
                                await _load_file_b64(path),
                                media="audio/mpeg",
                            )
                        )

                    elif path.endswith(".wav"):
                        parts.append(
                            MediaContent.base64(
                                await _load_file_b64(path),
                                media="audio/wav",
                            )
                        )

                    elif path.endswith(".mp4"):
                        parts.append(
                            MediaContent.base64(
                                await _load_file_b64(path),
                                media="video/mp4",
                            )
                        )

                else:
                    raise NotImplementedError("Unsupported file content")

    return MultimodalContent.of(*parts)


def _as_message_content(  # noqa: C901, PLR0912
    content: MultimodalContent,
) -> list[Text | Image | Audio | Video | Component]:
    result: list[Text | Image | Audio | Video | Component] = []
    for part in content.parts:
        match part:
            case TextContent() as text:
                result.append(Text(content=text.text))

            case MediaContent() as media:
                match media.kind:
                    case "image":
                        match media.source:
                            case str() as url:
                                result.append(Image(url=url))

                            case bytes() as data:
                                raise NotImplementedError("Base64 content is not supported yet")

                    case "audio":
                        match media.source:
                            case str() as url:
                                result.append(Audio(url=url))

                            case bytes() as data:
                                raise NotImplementedError("Base64 content is not supported yet")

                    case "video":
                        match media.source:
                            case str() as url:
                                result.append(Video(url=url))

                            case bytes() as data:
                                raise NotImplementedError("Base64 content is not supported yet")

            case DataModel() as data:
                result.append(Component(props=data.as_dict()))

    return result


if __name__ == "__main__":
    from chainlit.cli import run_chainlit

    run_chainlit(__file__)
