from asyncio import get_running_loop
from base64 import b64encode
from typing import Any, Final, Literal, cast

from chainlit import (
    Audio,
    ChatProfile,
    Component,
    ErrorMessage,
    File,
    Image,
    Message,
    Pdf,
    Starter,
    Step,
    Text,
    Video,
    on_chat_start,  # type: ignore  # type: ignore
    on_message,  # type: ignore  # type: ignore
    set_chat_profiles,  # type: ignore
    set_starters,  # type: ignore  # type: ignore
    user_session,
)
from draive import (
    LMM,
    AudioBase64Content,
    AudioDataContent,
    AudioURLContent,
    ConversationMessage,
    ConversationMessageChunk,
    DataModel,
    ImageBase64Content,
    ImageDataContent,
    ImageURLContent,
    MultimodalContent,
    ScopeDependencies,
    ScopeState,
    TextContent,
    TextEmbedding,
    Tokenization,
    ToolStatus,
    VideoBase64Content,
    VideoDataContent,
    VideoURLContent,
    VolatileAccumulativeMemory,
    ctx,
    load_env,
    metrics_log_reporter,
    setup_logging,
)
from draive.openai import (
    OpenAIChatConfig,
    OpenAIClient,
    OpenAIEmbeddingConfig,
    openai_embed_text,
    openai_lmm_invocation,
    openai_tokenize_text,
)
from features.chat import chat_respond
from integrations.network import NetworkClient

load_env()  # load env first if needed
setup_logging("demo", "metrics")


# define dependencies globally - it will be reused for all chats
# regardless of selected service selection
# those are definitions of external services access methods
dependencies: Final[ScopeDependencies] = ScopeDependencies(
    NetworkClient,
    OpenAIClient,
)


@set_chat_profiles
def prepare_profiles(user: Any) -> list[ChatProfile]:
    """
    Prepare chat profiles allowing to select service providers
    """

    return [
        ChatProfile(
            name="gpt-3.5-turbo",
            markdown_description="**GPT-3.5**\nText only with tools",
            default=True,
        ),
        ChatProfile(
            name="gpt-4o",
            markdown_description="**GPT-4**\nMultimodal with tools",
            default=False,
        ),
    ]


@set_starters
def prepare_starters(user: Any) -> list[Starter]:
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
        VolatileAccumulativeMemory[ConversationMessage]([], limit=12),
    )
    # select services based on current profile and form a base state for session
    config: OpenAIChatConfig
    match user_session.get("chat_profile"):  # pyright: ignore[reportUnknownMemberType]
        case "gpt-3.5-turbo":
            config = OpenAIChatConfig(
                model="gpt-3.5-turbo",
                temperature=0.75,
            )

        case "gpt-4o":
            config = OpenAIChatConfig(
                model="gpt-4o",
                temperature=0.75,
            )

        case other:  # pyright: ignore[reportUnknownVariableType]
            raise RuntimeError("Invalid profile %s", other)  # type: ignore

    state: ScopeState = ScopeState(
        LMM(invocation=openai_lmm_invocation),
        Tokenization(tokenize_text=openai_tokenize_text),
        TextEmbedding(embed=openai_embed_text),
        OpenAIEmbeddingConfig(
            model="text-embedding-3-small",
        ),
        config,
    )

    # use selected services by setting up session state
    user_session.set(  # pyright: ignore[reportUnknownMemberType]
        "state",
        state,
    )


@on_message
async def message(  # noqa: C901, PLR0912
    message: Message,
) -> None:
    """
    Handle incoming message and stream the response
    """

    # enter a new context for processing each message
    # using session state and shared dependencies
    async with ctx.new(
        "chat",
        state=user_session.get("state"),  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
        dependencies=dependencies,
        trace_reporting=metrics_log_reporter(),
    ):
        response_message: Message = Message(author="assistant", content="")
        await response_message.send()  # prepare message for streaming
        try:
            # request a chat conversation completion stream
            response_stream = await chat_respond(
                # convert message from chainlit to draive
                message=await _as_multimodal_content(
                    content=message.content,
                    elements=message.elements,  # pyright: ignore[reportArgumentType]
                ),
                memory=user_session.get("chat_memory"),  # pyright: ignore[reportUnknownMemberType, reportArgumentType]
            )

            # track tools execution to show progress items
            tool_steps: dict[str, Step] = {}
            async for part in response_stream:
                match part:  # consume each incoming stream part
                    case ConversationMessageChunk() as chunk:
                        for element in _as_message_content(chunk.content):
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

                    case ToolStatus() as tool_status:
                        ctx.log_debug("Received tool status: %s", tool_status)
                        # for a tool status add or update its progress indicator
                        step: Step
                        if current_step := tool_steps.get(tool_status.identifier):
                            step = current_step

                        else:
                            step: Step = Step(
                                id=tool_status.identifier,
                                name=tool_status.tool,
                                type="tool",
                            )
                            tool_steps[tool_status.identifier] = step

                            match tool_status.status:
                                case "STARTED":
                                    await step.send()

                                case "PROGRESS":
                                    if content := tool_status.content:
                                        # stream tool update status if provided
                                        await step.stream_token(str(content))

                                case "FINISHED":
                                    # finalize the status
                                    await step.update()

                                case "FAILED":
                                    # finalize indicating an error
                                    step.output = "ERROR"
                                    await step.update()

        except Exception as exc:
            ctx.log_error("Conversation failed", exception=exc)
            # replace the message with the error message as the result
            # not the best error handling but still handling
            await response_message.remove()
            await ErrorMessage(content=str(exc)).send()

        else:
            await response_message.update()  # finalize the message


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
                        ImageURLContent(
                            image_url=url,
                            mime_type=cast(
                                Literal["image/jpeg", "image/png", "image/gif"],
                                image.mime
                                if image.mime in ["image/jpeg", "image/png", "image/gif"]
                                else None,
                            ),
                        )
                    )

                elif path := image.path:
                    parts.append(
                        ImageBase64Content(
                            image_base64=await _load_file_b64(path),
                            mime_type=cast(
                                Literal["image/jpeg", "image/png", "image/gif"],
                                image.mime
                                if image.mime in ["image/jpeg", "image/png", "image/gif"]
                                else None,
                            ),
                        )
                    )

                else:
                    raise NotImplementedError("Unsupported image content")

            case Audio() as audio:
                if url := audio.url:
                    parts.append(
                        AudioURLContent(
                            audio_url=url,
                            mime_type=audio.mime,
                        )
                    )

                elif path := audio.path:
                    parts.append(
                        AudioBase64Content(
                            audio_base64=await _load_file_b64(path),
                            mime_type=audio.mime,
                        )
                    )

                else:
                    raise NotImplementedError("Unsupported audio content")

            case Video() as video:
                if url := video.url:
                    parts.append(
                        VideoURLContent(
                            video_url=url,
                            mime_type=video.mime,
                        )
                    )

                elif path := video.path:
                    parts.append(
                        VideoBase64Content(
                            video_base64=await _load_file_b64(path),
                            mime_type=video.mime,
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
                            AudioBase64Content(
                                audio_base64=await _load_file_b64(path),
                                mime_type="audio/mp3",
                            )
                        )

                    elif path.endswith(".wav"):
                        parts.append(
                            AudioBase64Content(
                                audio_base64=await _load_file_b64(path),
                                mime_type="audio/wav",
                            )
                        )

                    elif path.endswith(".mp4"):
                        parts.append(
                            VideoBase64Content(
                                video_base64=await _load_file_b64(path),
                                mime_type="video/mp4",
                            )
                        )

                else:
                    raise NotImplementedError("Unsupported file content")

    return MultimodalContent.of(*parts)


def _as_message_content(  # noqa: C901
    content: MultimodalContent,
) -> list[Text | Image | Audio | Video | Component]:
    result: list[Text | Image | Audio | Video | Component] = []
    for part in content.parts:
        match part:
            case TextContent() as text:
                result.append(Text(content=text.text))

            case ImageURLContent() as image_url:
                result.append(Image(url=image_url.image_url))

            case ImageBase64Content():
                raise NotImplementedError("Base64 content is not supported yet")

            case ImageDataContent():
                raise NotImplementedError("Bytes content is not supported yet")

            case AudioURLContent() as audio_url:
                result.append(Audio(url=audio_url.audio_url))

            case AudioBase64Content():
                raise NotImplementedError("Base64 content is not supported yet")

            case AudioDataContent():
                raise NotImplementedError("Bytes content is not supported yet")

            case VideoURLContent() as video_url:
                result.append(Video(url=video_url.video_url))

            case VideoBase64Content():
                raise NotImplementedError("Base64 content is not supported yet")

            case VideoDataContent():
                raise NotImplementedError("Bytes content is not supported yet")

            case DataModel() as data:
                result.append(Component(props=data.as_dict()))

    return result


if __name__ == "__main__":
    from chainlit.cli import run_chainlit

    run_chainlit(__file__)
