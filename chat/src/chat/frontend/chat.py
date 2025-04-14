from base64 import b64decode, b64encode
from collections.abc import Sequence
from typing import Any, cast

from chainlit import (
    Audio,
    ChatSettings,
    CustomElement,
    ErrorMessage,
    File,
    Image,
    Message,
    Pdf,
    Starter,
    Text,
    User,
    Video,
    data_layer,
    on_chat_end,
    on_chat_resume,
    on_chat_start,
    on_message,
    on_settings_update,
    password_auth_callback,
    set_starters,
    user_session,
)
from chainlit.input_widget import TextInput
from chainlit.types import ThreadDict
from draive import (
    Conversation,
    ConversationMessage,
    DataModel,
    MediaData,
    MediaReference,
    Memory,
    MetricsLogger,
    MultimodalContent,
    ProcessingEvent,
    State,
    TextContent,
    asynchronous,
    ctx,
)
from draive.mcp import MCPClient
from haiway.utils.env import getenv_str

from features.chat import chat_stream
from solutions.data_layer import PostgresDataLayer, normalized_image


@password_auth_callback
async def auth_callback(
    username: str,
    password: str,
) -> User | None:
    if (username, password) == ("username", getenv_str("CHAT_PASSWORD", required=True)):
        return User(
            identifier="username",
            display_name="User",
        )

    else:
        return None


@set_starters
async def prepare_starters(user: Any) -> list[Starter]:
    return []


@on_chat_start
async def start() -> None:
    ctx.log_debug("Starting chat session...")
    await ChatSettings(
        [
            TextInput(
                id="mcp_server",
                label="MCP Server stdio run command or https address for SSE",
                placeholder="npx -y @modelcontextprotocol/server-filesystem /local/path/",
            ),
        ]
    ).send()
    user_session.set("mcp_client", None)
    user_session.set("mcp_state", ())


@on_chat_end
async def end() -> None:
    ctx.log_debug("...closing chat session...")
    if client := user_session.get("mcp_client"):
        ctx.log_debug("...closing mcp client...")
        await client.__aexit__(None, None, None)


@on_settings_update
async def update_settings(settings: dict[str, Any]) -> None:
    mcp_server: str | None = settings.get("mcp_server")
    ctx.log_debug("Chat settings updated!")
    if client := user_session.get("mcp_client"):
        if client.identifier == mcp_server:
            ctx.log_debug("Keeping current mcp client...")
            return  # keep the same one

        ctx.log_debug("Closing current mcp client...")
        await client.__aexit__(None, None, None)

    if mcp_server:
        ctx.log_debug("...preparing new mcp client...")
        mcp_server = mcp_server.strip()
        mcp_client: MCPClient
        if mcp_server.startswith("http"):
            command_parts = mcp_server.split(" ")
            mcp_client = MCPClient.sse(
                identifier=mcp_server,
                url=mcp_server,
            )

        else:
            command_parts = mcp_server.split(" ")
            mcp_client = MCPClient.stdio(
                identifier=mcp_server,
                command=command_parts[0],
                args=command_parts[1:],
            )

        user_session.set("mcp_client", mcp_client)
        user_session.set("mcp_state", await mcp_client.__aenter__())

    else:
        ctx.log_debug("...removing mcp client...")
        user_session.set("mcp_client", None)
        user_session.set("mcp_state", ())


@on_chat_resume
async def resume_chat(
    thread: ThreadDict,
) -> None:
    try:
        memory: Memory[Sequence[ConversationMessage], ConversationMessage] = (
            Memory.accumulative_volatile()
        )
        for message in thread["steps"]:
            match message:
                case {"type": "user_message", "output": str() as content, "parentId": None}:
                    elements: list[MultimodalContent] = [
                        _element_content(element)  # pyright: ignore[reportArgumentType]
                        for element in thread["elements"]  # pyright: ignore[reportOptionalIterable]
                        if element["forId"] == message["id"]  # pyright: ignore[reportTypedDictNotRequiredAccess]
                    ]

                    await memory.remember(
                        ConversationMessage.user(content=MultimodalContent.of(content, *elements))
                    )

                case {"output": str() as content, "parentId": None}:
                    await memory.remember(ConversationMessage.model(content=content))

                case _:
                    pass  # ignore

        user_session.set("memory", memory)  # pyright: ignore

    except Exception as exc:
        ctx.log_error(
            "Recreating message history failed",
            exception=exc,
        )


@on_message
async def handle_message(
    message: Message,
) -> None:
    try:
        mcp_state: Sequence[State] = user_session.get("mcp_state", ())  # pyright: ignore[reportAssignmentType]
        memory: Memory | None = user_session.get("memory")
        if memory is None:
            memory = Memory.accumulative_volatile()
            user_session.set("memory", memory)

        async with ctx.scope(
            "message",
            *mcp_state,
            Conversation(memory=memory),
            metrics=MetricsLogger.handler(),
        ):
            response_message = Message(
                author="assistant",
                content="",
            )

            async for chunk in await chat_stream(
                message=await _as_multimodal_content(
                    content=message.content,
                    elements=message.elements,  # pyright: ignore[reportArgumentType]
                ),
            ):
                match chunk:
                    case ProcessingEvent():
                        pass  # we are not supporting events yet

                    case chunk:
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

            await response_message.send()  # end streaming

    except Exception as exc:
        ctx.log_error(
            "Handling message failed",
            exception=exc,
        )
        await ErrorMessage(author="error", content=str(exc)).send()


# helper for getting base64 data from the local file
@asynchronous
def _load_image_b64(path: str) -> str:
    with open(path, "rb") as file:
        return b64encode(normalized_image(file.read())).decode("utf-8")


def _element_content(
    element: dict[str, Any],
    /,
) -> MultimodalContent:
    match element:
        case {
            "mime": "text/plain",
            "url": str() as url,
        } if url.startswith("data"):
            return MultimodalContent.of(
                b64decode(url.removeprefix("data:text/plain;base64,")).decode()
            )

        case {
            "mime": "image/png" | "image/jpeg" | "image/jpg" as mime,
            "url": str() as url,
        } if url.startswith("data"):
            return MultimodalContent.of(
                MediaData.of(
                    url.removeprefix(f"data:{mime};base64,"),
                    media=cast(Any, mime),
                )
            )

        case other:  # skip unknown through empty content
            ctx.log_error(f"Received unsupported content:\n{other}")
            return MultimodalContent.of()


async def _as_multimodal_content(
    content: str,
    elements: list[Text | Image | Audio | Video | Pdf | File],
) -> MultimodalContent:
    parts: list[Any] = [content]
    for element in elements:
        match element:
            case Text() as text:
                parts.append(text.content)

            case Image() as image:
                if url := image.url:
                    parts.append(
                        MediaReference.of(
                            url,
                            media="image",
                        )
                    )

                elif path := image.path:
                    parts.append(
                        MediaData.of(
                            await _load_image_b64(path),
                            media="image/png",
                        )
                    )

                else:
                    raise NotImplementedError("Unsupported image content")

            case _:
                raise NotImplementedError("Unsupported content")

    return MultimodalContent.of(*parts)


def _as_message_content(  # noqa: C901
    content: MultimodalContent,
) -> list[Text | Image | Audio | Video | CustomElement]:
    result: list[Text | Image | Audio | Video | CustomElement] = []
    for part in content.parts:
        match part:
            case TextContent() as text:
                result.append(Text(content=text.text))

            case MediaData() as media_data:
                match media_data.kind:
                    case "image":
                        result.append(
                            Image(
                                url=f"data:{media_data.media};base64,{b64encode(media_data.data)}"
                            )
                        )

                    case "audio":
                        result.append(
                            Audio(
                                url=f"data:{media_data.media};base64,{b64encode(media_data.data)}"
                            )
                        )

                    case "video":
                        result.append(
                            Video(
                                url=f"data:{media_data.media};base64,{b64encode(media_data.data)}"
                            )
                        )

            case MediaReference() as media_reference:
                match media_reference.kind:
                    case "image":
                        result.append(Image(url=media_reference.uri))

                    case "audio":
                        result.append(Audio(url=media_reference.uri))

                    case "video":
                        result.append(Video(url=media_reference.uri))

            case DataModel() as data:
                result.append(CustomElement(props=data.as_dict()))

    return result


@data_layer
def setup_postgres() -> PostgresDataLayer:
    # setup chainlit data layer - https://docs.chainlit.io/data-persistence/custom
    return PostgresDataLayer()
