from base64 import b64decode
from collections.abc import Sequence
from io import BytesIO
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
    ConversationMessage,
    DataModel,
    GuardrailsModerationException,
    MultimodalContent,
    State,
    TextContent,
    as_dict,
    asynchronous,
    ctx,
)
from draive.mcp import MCPClient
from draive.resources import ResourceContent, ResourceReference
from haiway import LoggerObservability, getenv_str
from PIL import Image as PILImage
from PIL import UnidentifiedImageError

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
        memory: list[ConversationMessage] = []
        for message in thread["steps"]:
            match message:
                case {"type": "user_message", "output": str() as content, "parentId": None}:
                    elements: list[MultimodalContent] = [
                        _element_content(element)  # pyright: ignore[reportArgumentType]
                        for element in thread["elements"]  # pyright: ignore[reportOptionalIterable]
                        if element["forId"] == message["id"]  # pyright: ignore[reportTypedDictNotRequiredAccess]
                    ]

                    memory.append(
                        ConversationMessage.user(content=MultimodalContent.of(content, *elements))
                    )

                case {"output": str() as content, "parentId": None}:
                    memory.append(ConversationMessage.model(content=content))

                case _:
                    pass  # ignore

        user_session.set("memory", memory)

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
        history: list[ConversationMessage] | None = cast(
            list[ConversationMessage] | None,
            user_session.get("memory"),
        )
        if history is None:
            history = []
            user_session.set("memory", history)

        async with ctx.scope(
            "message",
            *mcp_state,
            observability=LoggerObservability(),
        ):
            user_conversation_message = ConversationMessage.user(
                content=await _as_multimodal_content(
                    content=message.content,
                    elements=message.elements,  # pyright: ignore[reportArgumentType]
                )
            )
            response_message = Message(
                author="assistant",
                content="",
            )

            streamed_chunks: list[MultimodalContent] = []
            async for chunk in await chat_stream(
                message=user_conversation_message,
                memory=history,
            ):
                if not chunk.content.parts:
                    continue

                streamed_chunks.append(chunk.content)
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

            history.extend(
                (
                    user_conversation_message,
                    ConversationMessage.model(content=_merge_multimodal_chunks(streamed_chunks)),
                )
            )
            user_session.set("memory", history)

    except GuardrailsModerationException as exc:
        ctx.log_error(
            "Guardrails exception",
            exception=exc,
        )
        await ErrorMessage(
            author="error",
            content=exc.replacement.to_str()
            if exc.replacement is not None
            else f"Guardrails issue: {','.join(exc.violations)}",
        ).send()

    except Exception as exc:
        ctx.log_error(
            "Handling message failed",
            exception=exc,
        )
        await ErrorMessage(author="error", content=str(exc)).send()


# helper for loading image bytes and retaining mime information from local files
@asynchronous
def _load_image_bytes(path: str) -> tuple[bytes, str]:
    with open(path, "rb") as file:
        data = normalized_image(file.read())

    try:
        with PILImage.open(BytesIO(data)) as pil_image:
            format_name = pil_image.format
            mime_type = PILImage.MIME.get(format_name or "")

            if not mime_type:
                converted = (
                    pil_image
                    if pil_image.mode in ("RGB", "RGBA", "L")
                    else pil_image.convert("RGBA")
                )
                buffer = BytesIO()
                converted.save(buffer, format="PNG")
                data = buffer.getvalue()
                mime_type = "image/png"

    except UnidentifiedImageError as exc:
        raise ValueError(f"Unsupported image provided at {path}") from exc

    return data, mime_type


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
                ResourceContent.of(
                    b64decode(url.removeprefix(f"data:{mime};base64,")),
                    mime_type=mime,
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
                        ResourceReference.of(
                            url,
                            mime_type="image",
                        )
                    )

                elif path := image.path:
                    image_bytes, mime_type = await _load_image_bytes(path)
                    parts.append(
                        ResourceContent.of(
                            image_bytes,
                            mime_type=mime_type,
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

            case ResourceContent() as resource_content:
                if resource_content.mime_type.startswith("image"):
                    result.append(Image(url=resource_content.to_data_uri()))

                elif resource_content.mime_type.startswith("audio"):
                    result.append(Audio(url=resource_content.to_data_uri()))

                elif resource_content.mime_type.startswith("video"):
                    result.append(Video(url=resource_content.to_data_uri()))

            case ResourceReference() as resource_reference:
                mime_type = resource_reference.mime_type or ""
                if mime_type.startswith("audio"):
                    result.append(Audio(url=resource_reference.uri))

                elif mime_type.startswith("video"):
                    result.append(Video(url=resource_reference.uri))

                else:
                    result.append(Image(url=resource_reference.uri))

            case DataModel() as data:
                result.append(CustomElement(props=as_dict(data.to_mapping())))

    return result


@data_layer
def setup_postgres() -> PostgresDataLayer:
    # setup chainlit data layer - https://docs.chainlit.io/data-persistence/custom
    return PostgresDataLayer()


def _merge_multimodal_chunks(
    chunks: Sequence[MultimodalContent],
) -> MultimodalContent:
    if not chunks:
        return MultimodalContent.of()

    parts: list[Any] = []
    for chunk in chunks:
        parts.extend(chunk.parts)

    return MultimodalContent.of(*parts)
