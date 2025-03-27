from base64 import b64decode, b64encode
from collections.abc import Sequence
from typing import Any, cast

from chainlit import (
    Audio,
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
    on_chat_resume,  # type: ignore
    on_message,  # type: ignore
    password_auth_callback,  # type: ignore
    set_starters,  # type: ignore
    user_session,
)
from chainlit.types import ThreadDict
from chainlit.utils import mount_chainlit
from draive import (
    Conversation,
    ConversationMessage,
    DataModel,
    MediaContent,
    Memory,
    MetricsLogger,
    MultimodalContent,
    ProcessingEvent,
    TextContent,
    asynchronous,
    ctx,
)
from fastapi import FastAPI

from features.chat import chat_stream
from solutions.data_layer import PostgresDataLayer, normalized_image

__all__ = [
    "setup_frontend",
]


@password_auth_callback
async def auth_callback(username: str, password: str) -> User | None:
    # TODO: temporary auth for using data layer
    if (username, password) == ("username", "password"):
        return User(identifier="username", display_name="Tester")

    else:
        return None


@set_starters
async def prepare_starters(user: Any) -> list[Starter]:
    return []


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
        memory: Memory | None = user_session.get("memory")  # pyright: ignore
        if memory is None:
            memory = Memory.accumulative_volatile()  # pyright: ignore
            user_session.set("memory", memory)  # pyright: ignore
        async with ctx.scope(
            "message",
            Conversation(memory=memory),  # pyright: ignore
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
                MediaContent.base64(
                    url.removeprefix(f"data:{mime};base64,"),
                    media=cast(Any, mime),
                )
            )

        case _:  # skip unknown through empty content
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
                        MediaContent.url(
                            url,
                            media="image",
                        )
                    )

                elif path := image.path:
                    parts.append(
                        MediaContent.base64(
                            await _load_image_b64(path),
                            media="image/png",
                        )
                    )

                else:
                    raise NotImplementedError("Unsupported image content")

            case _:
                raise NotImplementedError("Unsupported content")

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


@data_layer
def setup_postgres() -> PostgresDataLayer:
    # setup chainlit data layer - https://docs.chainlit.io/data-persistence/custom
    return PostgresDataLayer()


def setup_frontend(app: FastAPI) -> None:
    mount_chainlit(
        app=app,
        target="src/chat/frontend/chat.py",
        path="",
    )
