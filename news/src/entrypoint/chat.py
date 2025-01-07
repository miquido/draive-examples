from asyncio import get_running_loop
from base64 import b64encode
from typing import Any, cast

from chainlit import (
    Audio,
    ChatProfile,
    CustomElement,
    ErrorMessage,
    File,
    Image,
    Message,
    Pdf,
    Starter,
    Text,
    Video,
    on_chat_start,  # type: ignore  # type: ignore
    on_message,  # type: ignore  # type: ignore
    set_chat_profiles,  # type: ignore
    set_starters,  # type: ignore  # type: ignore
    user_session,
)
from draive import (
    DataModel,
    MediaContent,
    Memory,
    MetricsLogger,
    MultimodalContent,
    State,
    TextContent,
    ctx,
    load_env,
    setup_logging,
)
from draive.openai import (
    OpenAIChatConfig,
    OpenAIEmbeddingConfig,
    openai_lmm,
    openai_text_embedding,
    openai_tokenizer,
)

from features.chat import chat_respond
from integrations.network import NetworkClient

load_env()  # load env first if needed
setup_logging("demo", "metrics")


@set_chat_profiles  # pyright: ignore[reportArgumentType]
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
    ]


@set_starters  # pyright: ignore[reportArgumentType]
async def prepare_starters(user: Any) -> list[Starter]:
    """
    List of starter messages for the chat, can be used for a common task shortcuts
    or as a showcase of the implemented features.
    """

    return [
        Starter(
            label="LLMs",
            message="Prepare a news page with latest advancements in LLM field",
        ),
        Starter(
            label="deepnewz",
            message="Show me the latest news from https://deepnewz.com",
        ),
    ]


@on_chat_start
async def prepare() -> None:
    """
    Prepare chat session which includes preparing a set of dependencies
    matching selected profile (services provider) and settings.
    """

    # prepare chat session memory - we are using volatile memory
    # which will return up to 12 last messages to the LLM context
    user_session.set(  # pyright: ignore[reportUnknownMemberType]
        "chat_memory",
        Memory.accumulative_volatile(limit=12),
    )
    # select services based on current profile and form a base state for session
    config: OpenAIChatConfig
    match user_session.get("chat_profile"):  # pyright: ignore[reportUnknownMemberType]
        case "gpt-4o-mini":
            config = OpenAIChatConfig(
                model="gpt-4o-mini",
                temperature=0.75,
                max_tokens=4096,
            )

        case "gpt-4o":
            config = OpenAIChatConfig(
                model="gpt-4o",
                temperature=0.75,
            )

        case other:  # pyright: ignore[reportUnknownVariableType]
            raise RuntimeError("Invalid profile %s", other)  # type: ignore

    state: list[State] = [
        openai_lmm(),
        openai_text_embedding(),
        openai_tokenizer("gpt-4o-mini"),
        OpenAIEmbeddingConfig(
            model="text-embedding-3-small",
        ),
        config,
        await NetworkClient.prepare().initialize(),
    ]

    # use selected services by setting up session state
    user_session.set(  # pyright: ignore[reportUnknownMemberType]
        "state",
        state,
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
        metrics=MetricsLogger.handler(),
    ):
        try:
            # request a chat conversation completion stream
            response = await chat_respond(
                # convert message from chainlit to draive
                message=await _as_multimodal_content(
                    content=message.content,
                    elements=message.elements,  # pyright: ignore[reportArgumentType]
                ),
                memory=user_session.get("chat_memory"),  # pyright: ignore[reportUnknownMemberType, reportArgumentType]
            )
            await Message(
                author="assistant",
                content="",
                elements=_as_message_content(response.content),
            ).send()

        except Exception as exc:
            ctx.log_error("Conversation failed", exception=exc)
            # replace the message with the error message as the result
            # not the best error handling but still handling
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

            case Pdf():
                raise NotImplementedError("PDF input is not supported")

            case File() as file:
                if path := file.path:
                    if path.endswith(".pdf"):
                        raise NotImplementedError("PDF input is not supported")

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
) -> list[Text | Image | Audio | Video | CustomElement]:
    result: list[Text | Image | Audio | Video | CustomElement] = []
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
                result.append(CustomElement(props=data.as_dict()))

    return result


if __name__ == "__main__":
    from chainlit.cli import run_chainlit

    run_chainlit(__file__)
