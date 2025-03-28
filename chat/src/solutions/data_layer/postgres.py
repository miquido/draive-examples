import json
from base64 import b64encode
from collections.abc import Sequence
from datetime import datetime
from typing import Any, cast
from uuid import UUID

import aiofiles
from chainlit.data import queue_until_user_message
from chainlit.data.base import BaseDataLayer
from chainlit.element import Element, ElementDict, ElementDisplay, ElementSize, ElementType
from chainlit.step import StepDict
from chainlit.types import (
    Feedback,
    PageInfo,
    PaginatedResponse,
    Pagination,
    ThreadDict,
    ThreadFilter,
)
from chainlit.user import PersistedUser, User
from draive import ctx
from literalai.observability.step import StepType

from integrations.postgres import Postgres, PostgresConnection, PostgresRow
from solutions.data_layer.images import normalized_image

__all__ = [
    "PostgresDataLayer",
    "fetch_element_content",
]


class PostgresDataLayer(BaseDataLayer):
    async def get_user(
        self,
        identifier: str,
    ) -> PersistedUser | None:
        ctx.log_debug(f"Accessing user ({identifier}) data...")
        try:
            async with ctx.scope("user-access", disposables=(Postgres.connection(),)):
                ctx.log_debug("...fetching user data...")
                record: PostgresRow | None = await PostgresConnection.fetch_one(
                    SELECT_USER_QUERY,
                    identifier,
                )

                if record is None:
                    ctx.log_info(f"...attempting to access missing user ({identifier}) data...")
                    return None

                ctx.log_debug("...decoding user data...")
                return self._decode_user(record)

        except Exception as exc:
            ctx.log_error(
                f"...accessing user ({identifier}) data failed...",
                exception=exc,
            )
            raise exc

        finally:
            ctx.log_debug("...accessing user data finished!")

    async def create_user(
        self,
        user: User,
    ) -> PersistedUser | None:
        ctx.log_debug(f"Creating user ({user.identifier})...")
        try:
            async with ctx.scope("creating-user", disposables=(Postgres.connection(),)):
                ctx.log_debug("...inserting user data...")
                await PostgresConnection.fetch(
                    UPSERT_USER_QUERY,
                    user.identifier,
                    json.dumps(user.metadata) if user.metadata else None,  # pyright: ignore
                )

                ctx.log_debug("...fetching user data...")
                record: PostgresRow | None = await PostgresConnection.fetch_one(
                    SELECT_USER_QUERY,
                    user.identifier,
                )

                if record is None:
                    ctx.log_info(
                        f"...attempting to access missing user ({user.identifier}) data..."
                    )
                    return None

                ctx.log_debug("...decoding user data...")
                return self._decode_user(record)

        except Exception as exc:
            ctx.log_error(
                f"...creating user ({user.identifier}) failed...",
                exception=exc,
            )
            raise exc

        finally:
            ctx.log_debug("...creating user finished!")

    def _decode_user(
        self,
        record: PostgresRow,
    ) -> PersistedUser:
        match record:
            case {
                "id": UUID() as id,
                "identifier": str() as identifier,
                "created": datetime() as created,
                "metadata": str() | None as metadata,
            }:
                return PersistedUser(
                    id=id.hex,
                    identifier=identifier,
                    createdAt=created.isoformat(),
                    metadata=json.loads(metadata) if metadata is not None else {},
                )

            case other:
                raise ValueError(f"Invalid user data: {other}")

    async def get_thread_author(
        self,
        thread_id: str,
    ) -> str:
        ctx.log_debug(f"Accessing thread ({thread_id}) author...")
        try:
            async with ctx.scope("author-data", disposables=(Postgres.connection(),)):
                ctx.log_debug("...fetching author data...")
                record: PostgresRow | None = await PostgresConnection.fetch_one(
                    SELECT_THREAD_AUTHOR_QUERY,
                    UUID(hex=thread_id),
                )
                if record is None:
                    raise ValueError(f"Thread ({thread_id}) author not found")

                ctx.log_debug("...decoding author data...")
                match record:
                    case {"user_identifier": str() as user_identifier}:
                        return user_identifier

                    case other:
                        raise ValueError(f"Invalid thread author data: {other}")

        except Exception as exc:
            ctx.log_error(
                f"...accessing thread ({thread_id}) author failed...",
                exception=exc,
            )
            raise exc

        finally:
            ctx.log_debug("...accessing thread author finished!")

    async def list_threads(
        self,
        pagination: Pagination,
        filters: ThreadFilter,
    ) -> PaginatedResponse[ThreadDict]:
        ctx.log_debug(f"Accessing user ({filters.userId}) threads...")
        try:
            limit: int = pagination.first or 10
            async with ctx.scope("threads-data", disposables=(Postgres.connection(),)):
                ctx.log_debug("...fetching threads data...")
                records: Sequence[PostgresRow] = await PostgresConnection.fetch(
                    SELECT_USER_THREADS_QUERY,
                    UUID(hex=filters.userId),
                    UUID(hex=pagination.cursor) if pagination.cursor else None,
                    filters.search,
                    limit,
                )

                ctx.log_debug("...decoding threads data...")
                threads: list[ThreadDict] = []
                for record in records:
                    thread: ThreadDict = self._decode_thread(record)
                    thread["elements"] = await self.get_thread_elements(
                        thread_id=thread["id"],
                    )
                    thread["steps"] = await self.get_thread_steps(
                        thread_id=thread["id"],
                    )
                    threads.append(thread)

                return PaginatedResponse(
                    data=threads,
                    pageInfo=PageInfo(
                        hasNextPage=len(threads) >= limit,
                        startCursor=threads[0]["id"] if threads else None,
                        endCursor=threads[-1]["id"] if threads else None,
                    ),
                )

        except Exception as exc:
            ctx.log_error(
                f"...accessing user ({filters.userId}) threads failed...",
                exception=exc,
            )
            raise exc

        finally:
            ctx.log_debug("...accessing user threads finished!")

    async def get_thread(
        self,
        thread_id: str,
    ) -> ThreadDict:
        ctx.log_debug(f"Accessing thread ({thread_id}) data...")
        try:
            async with ctx.scope("thread-data", disposables=(Postgres.connection(),)):
                ctx.log_debug("...fetching thread data...")
                record: PostgresRow | None = await PostgresConnection.fetch_one(
                    SELECT_THREAD_QUERY,
                    UUID(hex=thread_id),
                )
                if record is None:
                    raise ValueError(f"Thread not found for thread_id {thread_id}")

                ctx.log_debug("...decoding thread data...")
                thread: ThreadDict = self._decode_thread(record)

                thread["elements"] = await self.get_thread_elements(
                    thread_id=thread_id,
                )
                thread["steps"] = await self.get_thread_steps(
                    thread_id=thread_id,
                )

                return thread

        except Exception as exc:
            ctx.log_error(
                f"...accessing thread ({thread_id}) data failed...",
                exception=exc,
            )
            raise exc

        finally:
            ctx.log_debug("...accessing thread data finished!")

    def _decode_thread(
        self,
        record: PostgresRow,
    ) -> ThreadDict:
        match record:
            case {
                "id": UUID() as id,
                "created": datetime() as created,
                "user_id": UUID() as user_id,
                "user_identifier": str() as user_identifier,
                "name": str() | None as name,
                "tags": list()
                | None as tags,  # pyright: ignore
                "metadata": str() | None as metadata,
            }:
                return ThreadDict(
                    id=id.hex,
                    createdAt=created.isoformat(),
                    userId=user_id.hex,
                    userIdentifier=user_identifier,
                    name=name,
                    tags=tags,  # pyright: ignore
                    elements=[],
                    steps=[],
                    metadata=json.loads(metadata) if metadata is not None else {},
                )

            case _:
                raise ValueError(f"Invalid thread data: {record}")

    async def get_thread_elements(
        self,
        *,
        thread_id: str,
    ) -> list[ElementDict]:
        ctx.log_debug("...fetching thread elements data...")
        records: Sequence[PostgresRow] = await PostgresConnection.fetch(
            SELECT_THREAD_ELEMENTS_QUERY,
            UUID(hex=thread_id),
        )
        ctx.log_debug("...decoding thread elements data...")
        return [self._decode_element(record) for record in records]

    async def get_thread_steps(
        self,
        *,
        thread_id: str,
    ) -> list[StepDict]:
        ctx.log_debug("...fetching thread steps data...")
        records: Sequence[PostgresRow] = await PostgresConnection.fetch(
            SELECT_THREAD_STEPS_QUERY,
            UUID(hex=thread_id),
        )
        ctx.log_debug("...decoding thread steps data...")
        return [self._decode_step(record) for record in records]

    async def delete_thread(
        self,
        thread_id: str,
    ) -> None:
        ctx.log_debug(f"Deleting thread ({thread_id}) data...")
        try:
            async with ctx.scope("deleting-thread", disposables=(Postgres.connection(),)):
                await PostgresConnection.execute(
                    DELETE_THREAD_QUERY,
                    UUID(hex=thread_id),
                )

        except Exception as exc:
            ctx.log_error(
                f"...deleting thread ({thread_id}) data failed...",
                exception=exc,
            )
            raise exc

        finally:
            ctx.log_debug("...deleting thread data finished!")

    async def update_thread(
        self,
        thread_id: str,
        name: str | None = None,
        user_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ):
        ctx.log_debug(f"Updating thread ({thread_id})...")
        try:
            async with ctx.scope("updating-thread", disposables=(Postgres.connection(),)):
                await PostgresConnection.execute(
                    UPSERT_THREAD_QUERY,
                    UUID(hex=thread_id),
                    name
                    if name is not None
                    else metadata.get("name")
                    if metadata is not None
                    else None,
                    UUID(hex=user_id) if user_id is not None else None,
                    tags,
                    json.dumps(metadata) if metadata is not None else None,
                )

        except Exception as exc:
            ctx.log_error(
                f"...updating thread ({thread_id}) data failed...",
                exception=exc,
            )
            raise exc

        finally:
            ctx.log_debug("...updating thread data finished!")

    @queue_until_user_message()
    async def create_element(
        self,
        element: Element,
    ) -> None:
        ctx.log_debug(f"Creating thread ({element.thread_id}) element...")
        try:
            content: bytes | None = None
            if element.path:
                async with aiofiles.open(element.path, "rb") as f:
                    content = await f.read()

            elif element.url:
                content = None  # use current url

            elif element.content:
                content = (
                    element.content.encode()
                    if isinstance(element.content, str)
                    else element.content
                )

            else:
                raise ValueError("Element url, path or content must be provided")

            if content is None:
                raise ValueError("Missing content")

            if element.mime and element.mime.startswith("image"):
                content = normalized_image(content)

            async with ctx.scope("creating-thread", disposables=(Postgres.connection(),)):
                await PostgresConnection.fetch(
                    UPSERT_THREAD_ELEMENT_QUERY,
                    UUID(hex=element.id),  # id
                    UUID(hex=element.thread_id),  # thread_id
                    UUID(hex=element.for_id),  # message_id
                    element.type,  # type
                    element.mime,  # mime
                    element.name,  # name
                    element.url,  # url # TODO: make url for our storage
                    content,  # content
                    element.display,  # display
                    element.size,  # size
                )

        except Exception as exc:
            ctx.log_error(
                f"...creating thread ({element.thread_id}) element failed...",
                exception=exc,
            )
            raise exc

        finally:
            ctx.log_debug("...creating thread element finished!")

    async def get_element(
        self,
        thread_id: str,
        element_id: str,
    ) -> ElementDict | None:
        ctx.log_debug(f"Accessing element ({element_id}) of thread({thread_id})...")
        try:
            async with ctx.scope("accessing-thread-element", disposables=(Postgres.connection(),)):
                record: PostgresRow | None = await PostgresConnection.fetch_one(
                    SELECT_THREAD_ELEMENT_QUERY,
                    UUID(hex=element_id),
                )

            if record is None:
                raise ValueError(f"Thread element not found for thread_id {thread_id}")

            return self._decode_element(record)

        except Exception as exc:
            ctx.log_error(
                f"...accessing thread ({thread_id}) element ({element_id}) failed...",
                exception=exc,
            )
            raise exc

        finally:
            ctx.log_debug("...accessing thread element finished!")

    def _decode_element(
        self,
        record: PostgresRow,
    ) -> ElementDict:
        match record:
            case {
                "id": UUID() as element_id,
                "thread_id": UUID() as thread_id,
                "message_id": UUID() as message_id,
                "type": str() | None as element_type,
                "mime": str() | None as mime,
                "name": str() | None as name,
                "url": str() | None as url,
                "display": str() | None as display,
                "size": str() | None as size,
                "content": bytes() | None as content,
            }:
                return ElementDict(
                    id=element_id.hex,
                    threadId=thread_id.hex,
                    type=cast(ElementType, element_type) if element_type is not None else "text",
                    chainlitKey=None,
                    url=url
                    if url and url.startswith("http")
                    else f"data:{mime};base64,{b64encode(content).decode()}"
                    if content
                    else None,
                    objectKey=None,
                    name=name or "",
                    display=cast(ElementDisplay, display) if display is not None else "inline",
                    size=cast(ElementSize | None, size),
                    language=None,
                    page=None,
                    autoPlay=None,
                    playerConfig=None,
                    forId=message_id.hex,
                    mime=mime,
                    props=None,
                )

            case other:
                raise ValueError(f"Invalid thread element data: {other}")

    @queue_until_user_message()
    async def delete_element(
        self,
        element_id: str,
        thread_id: str | None = None,
    ) -> None:
        ctx.log_debug(f"Deleting thread ({thread_id}) element ({element_id})...")
        try:
            async with ctx.scope("deleting-thread", disposables=(Postgres.connection(),)):
                await PostgresConnection.execute(
                    DELETE_THREAD_ELEMENT_QUERY,
                    UUID(hex=thread_id),
                )

        except Exception as exc:
            ctx.log_error(
                f"...deleting thread ({thread_id}) element ({element_id}) failed...",
                exception=exc,
            )
            raise exc

        finally:
            ctx.log_debug("...deleting thread element finished!")

    @queue_until_user_message()
    async def create_step(
        self,
        step_dict: StepDict,
    ):
        await self.update_step(step_dict)

    @queue_until_user_message()
    async def update_step(
        self,
        step_dict: StepDict,
    ) -> None:
        ctx.log_debug(
            f"Updating thread step ({step_dict["id"]})..."  # pyright: ignore
        )
        try:
            step_dict["showInput"] = (  # from SQLAlchemy implementation
                str(step_dict.get("showInput", "")).lower()  # pyright: ignore
                if "showInput" in step_dict
                else None
            )
            async with ctx.scope("updating-thread-step", disposables=(Postgres.connection(),)):
                await PostgresConnection.fetch(
                    UPSERT_THREAD_STEP_QUERY,
                    UUID(hex=step_dict["id"]),  # id # pyright: ignore
                    datetime.fromisoformat(step_dict.get("createdAt"))  # created # pyright: ignore
                    if step_dict.get("createdAt")  # pyright: ignore
                    else None,
                    UUID(hex=step_dict["threadId"])  # thread_id # pyright: ignore
                    if step_dict.get("threadId")  # pyright: ignore
                    else None,
                    UUID(hex=step_dict["parentId"])  # pyright: ignore
                    if step_dict.get("parentId")  # pyright: ignore
                    else None,  # parent_id
                    step_dict.get("type"),  # type # pyright: ignore
                    step_dict.get("name"),  # name # pyright: ignore
                    step_dict.get("streaming"),  # streaming # pyright: ignore
                    step_dict.get("waitForAnswer"),  # wait_for_answer # pyright: ignore
                    step_dict.get("isError"),  # is_error # pyright: ignore
                    json.dumps(step_dict["metadata"])  # metadata # pyright: ignore
                    if step_dict.get("metadata")  # pyright: ignore
                    else None,
                    step_dict.get("tags"),  # tags # pyright: ignore
                    step_dict.get("input"),  # input # pyright: ignore
                    step_dict.get("output"),  # output # pyright: ignore
                    json.dumps(step_dict["generation"])  # generation # pyright: ignore
                    if step_dict.get("generation")  # pyright: ignore
                    else None,
                    step_dict.get("showInput"),  # show_input # pyright: ignore
                    step_dict.get("indent"),  # indent # pyright: ignore
                    datetime.fromisoformat(step_dict.get("start"))  # start_time # pyright: ignore
                    if step_dict.get("start")  # pyright: ignore
                    else None,
                    datetime.fromisoformat(step_dict.get("end"))  # end_time # pyright: ignore
                    if step_dict.get("end")  # pyright: ignore
                    else None,
                )

        except Exception as exc:
            ctx.log_error(
                f"...updating thread step ({step_dict["id"]}) failed...",  # pyright: ignore
                exception=exc,
            )
            raise exc

        finally:
            ctx.log_debug("...updating thread step finished!")

    def _decode_step(
        self,
        record: PostgresRow,
    ) -> StepDict:
        match record:
            case {
                "id": UUID() as step_id,
                "created": datetime() as created,
                "thread_id": UUID() as thread_id,
                "parent_id": UUID() | None as parent_id,
                "type": str() | None as step_type,
                "name": str() | None as name,
                "streaming": bool() | None as streaming,
                "wait_for_answer": bool() | None as wait_for_answer,
                "is_error": bool() | None as is_error,
                "metadata": str() | None as metadata,
                "tags": list()
                | None as tags,  # pyright: ignore
                "input": str() | None as input,
                "output": str() | None as output,
                "generation": str() | None as generation,
                "show_input": str() | None as show_input,
                "indent": int() | None as indent,
                "start_time": datetime() | None as start_time,
                "end_time": datetime() | None as end_time,
            }:
                return StepDict(
                    id=step_id.hex,
                    createdAt=created.isoformat(),
                    threadId=thread_id.hex,
                    parentId=parent_id.hex if parent_id else None,
                    type=cast(StepType, step_type),
                    name=name or "",
                    streaming=streaming or False,
                    waitForAnswer=wait_for_answer,
                    isError=is_error,
                    metadata=json.loads(metadata) if metadata is not None else {},
                    tags=tags,  # pyright: ignore
                    input=input or "",
                    output=output or "",
                    generation=json.loads(generation) if generation else None,
                    showInput=show_input,
                    indent=indent,
                    start=start_time.isoformat() if start_time else None,
                    end=end_time.isoformat() if end_time else None,
                )

            case other:
                raise ValueError(f"Invalid thread element data: {other}")

    @queue_until_user_message()
    async def delete_step(
        self,
        step_id: str,
    ) -> None:
        ctx.log_debug(f"Deleting thread step ({step_id})...")
        try:
            async with ctx.scope("user-access", disposables=(Postgres.connection(),)):
                await PostgresConnection.fetch(
                    DELETE_THREAD_STEP_QUERY,
                    UUID(hex=step_id),
                )

        except Exception as exc:
            ctx.log_error(
                f"...deleting thread step ({step_id}) failed...",
                exception=exc,
            )
            raise exc

        finally:
            ctx.log_debug("...deleting thread step finished!")

    # not implemented - ignore
    async def delete_feedback(
        self,
        feedback_id: str,
    ) -> bool:
        return True

    # not implemented - ignore
    async def upsert_feedback(
        self,
        feedback: Feedback,
    ) -> str:
        return ""

    # not implemented - ignore
    async def build_debug_url(self) -> str:
        return ""


async def fetch_element_content(
    element_id: str,
) -> bytes | None:
    ctx.log_debug(f"Accessing element ({element_id}) content...")
    try:
        async with ctx.scope("accessing-element", disposables=(Postgres.connection(),)):
            record: PostgresRow | None = await PostgresConnection.fetch_one(
                SELECT_THREAD_ELEMENT_CONTENT_QUERY,
                UUID(hex=element_id),
            )

        match record:
            case None:
                raise ValueError(f"Thread element content not found for element ({element_id})")

            case {"content": bytes() as content}:
                return content

            case other:
                raise ValueError(f"Invalid thread element content: {other}")

    except Exception as exc:
        ctx.log_error(
            f"...accessing thread element ({element_id}) failed...",
            exception=exc,
        )
        raise exc

    finally:
        ctx.log_debug("...accessing thread element finished!")


SELECT_USER_QUERY: str = """\
SELECT
    users.id AS id,
    users.identifier as identifier,
    users.created AS created,
    users.metadata AS metadata

FROM
    users

WHERE
    users.identifier = $1
;
"""

UPSERT_USER_QUERY: str = """\
INSERT INTO
    users (
        identifier,
        metadata
    )

VALUES
    (
        $1,
        $2
    )

ON CONFLICT
    (
        identifier
    )

DO UPDATE SET
    metadata = CASE
        WHEN excluded.metadata IS NOT NULL THEN excluded.metadata
        ELSE users.metadata
    END
;
"""

SELECT_THREAD_AUTHOR_QUERY: str = """\
SELECT
    users.identifier AS user_identifier

FROM
    threads

LEFT JOIN
    users

ON
    threads.user_id = users.id

WHERE
    threads.id = $1
;
"""

SELECT_THREAD_QUERY: str = """\
SELECT
    threads.id AS id,
    threads.created AS created,
    threads.name AS name,
    threads.user_id AS user_id,
    users.identifier AS user_identifier,
    threads.tags AS tags,
    threads.metadata AS metadata

FROM
    threads

LEFT JOIN
    users

ON
    threads.user_id = users.id

WHERE
    threads.id = $1
;
"""

SELECT_USER_THREADS_QUERY: str = """\
SELECT
    threads.id AS id,
    threads.created AS created,
    threads.name AS name,
    threads.user_id AS user_id,
    users.identifier AS user_identifier,
    threads.tags AS tags,
    threads.metadata AS metadata

FROM
    threads

LEFT JOIN
    users

ON
    threads.user_id = users.id

WHERE
    threads.user_id = $1

AND
    threads.id > COALESCE($2::UUID, '00000000-0000-0000-0000-000000000000'::UUID)

AND
    ($3::TEXT IS NULL OR threads.name ILIKE '%' || $3::TEXT || '%')

ORDER BY
    threads.created

    DESC

LIMIT
    $4
;
"""

UPSERT_THREAD_QUERY: str = """\
INSERT INTO
    threads (
        id,
        name,
        user_id,
        tags,
        metadata
    )

VALUES
    (
        $1,
        $2,
        $3,
        $4,
        $5
    )

ON CONFLICT
    (
        id
    )

DO UPDATE SET
    name = CASE
        WHEN excluded.name IS NOT NULL THEN excluded.name
        ELSE threads.name
    END,
    tags = CASE
        WHEN excluded.tags IS NOT NULL THEN excluded.tags
        ELSE threads.tags
    END,
    metadata = CASE
        WHEN excluded.metadata IS NOT NULL THEN excluded.metadata
        ELSE threads.metadata
    END
;
"""

DELETE_THREAD_QUERY: str = """\
DELETE FROM
    threads

WHERE
    threads.id = $1
;
"""

UPSERT_THREAD_ELEMENT_QUERY: str = """\
INSERT INTO
    elements (
        id,
        thread_id,
        message_id,
        type,
        mime,
        name,
        url,
        content,
        display,
        size
    )

VALUES
    (
        $1,
        $2,
        $3,
        $4,
        $5,
        $6,
        $7,
        $8,
        $9,
        $10
    )

ON CONFLICT
    (
        id
    )

DO UPDATE SET
    name = CASE
        WHEN excluded.name IS NOT NULL THEN excluded.name
        ELSE elements.name
    END,
    type = CASE
        WHEN excluded.type IS NOT NULL THEN excluded.type
        ELSE elements.type
    END,
    mime = CASE
        WHEN excluded.mime IS NOT NULL THEN excluded.mime
        ELSE elements.mime
    END,
    content = CASE
        WHEN excluded.content IS NOT NULL THEN excluded.content
        ELSE elements.content
    END,
    display = CASE
        WHEN excluded.display IS NOT NULL THEN excluded.display
        ELSE elements.display
    END,
    size = CASE
        WHEN excluded.size IS NOT NULL THEN excluded.size
        ELSE elements.size
    END
;
"""

SELECT_THREAD_ELEMENT_QUERY: str = """\
SELECT
    elements.id,
    elements.thread_id,
    elements.message_id,
    elements.type,
    elements.mime,
    elements.name,
    elements.url,
    elements.display,
    elements.size,
    elements.content

FROM
    elements

WHERE
    elements.id = $1
;
"""

SELECT_THREAD_ELEMENT_CONTENT_QUERY: str = """\
SELECT
    elements.id,
    elements.content

FROM
    elements

WHERE
    elements.id = $1
;
"""

SELECT_THREAD_ELEMENTS_QUERY: str = """\
SELECT
    elements.id,
    elements.thread_id,
    elements.message_id,
    elements.type,
    elements.mime,
    elements.name,
    elements.url,
    elements.content,
    elements.display,
    elements.size

FROM
    elements

WHERE
    elements.thread_id = $1

ORDER BY
    elements.created
;
"""

DELETE_THREAD_ELEMENT_QUERY: str = """\
DELETE FROM
    elements

WHERE
    elements.id = $1
;
"""

UPSERT_THREAD_STEP_QUERY: str = """\
INSERT INTO
    steps (
        id,
        created,
        thread_id,
        parent_id,
        type,
        name,
        streaming,
        wait_for_answer,
        is_error,
        metadata,
        tags,
        input,
        output,
        generation,
        show_input,
        indent,
        start_time,
        end_time
    )

VALUES
    (
        $1,
        $2,
        $3,
        $4,
        $5,
        $6,
        $7,
        $8,
        $9,
        $10,
        $11,
        $12,
        $13,
        $14,
        $15,
        $16,
        $17,
        $18
    )

ON CONFLICT
    (
        id
    )

DO UPDATE SET
    name = CASE
        WHEN excluded.name IS NOT NULL THEN excluded.name
        ELSE steps.name
    END,
    type = CASE
        WHEN excluded.type IS NOT NULL THEN excluded.type
        ELSE steps.type
    END,
    streaming = CASE
        WHEN excluded.streaming IS NOT NULL THEN excluded.streaming
        ELSE steps.streaming
    END,
    wait_for_answer = CASE
        WHEN excluded.wait_for_answer IS NOT NULL THEN excluded.wait_for_answer
        ELSE steps.wait_for_answer
    END,
    is_error = CASE
        WHEN excluded.is_error IS NOT NULL THEN excluded.is_error
        ELSE steps.is_error
    END,
    tags = CASE
        WHEN excluded.tags IS NOT NULL THEN excluded.tags
        ELSE steps.tags
    END,
    metadata = CASE
        WHEN excluded.metadata IS NOT NULL THEN excluded.metadata
        ELSE steps.metadata
    END,
    input = CASE
        WHEN excluded.input IS NOT NULL THEN excluded.input
        ELSE steps.input
    END,
    output = CASE
        WHEN excluded.output IS NOT NULL THEN excluded.output
        ELSE steps.output
    END,
    generation = CASE
        WHEN excluded.generation IS NOT NULL THEN excluded.generation
        ELSE steps.generation
    END,
    show_input = CASE
        WHEN excluded.show_input IS NOT NULL THEN excluded.show_input
        ELSE steps.show_input
    END,
    indent = CASE
        WHEN excluded.indent IS NOT NULL THEN excluded.indent
        ELSE steps.indent
    END,
    start_time = CASE
        WHEN excluded.start_time IS NOT NULL THEN excluded.start_time
        ELSE steps.start_time
    END,
    end_time = CASE
        WHEN excluded.end_time IS NOT NULL THEN excluded.end_time
        ELSE steps.end_time
    END
;
"""

SELECT_THREAD_STEP_QUERY: str = """\
SELECT
    steps.id,
    steps.created,
    steps.thread_id,
    steps.parent_id,
    steps.type,
    steps.name,
    steps.streaming,
    steps.wait_for_answer,
    steps.is_error,
    steps.metadata,
    steps.tags,
    steps.input,
    steps.output,
    steps.generation,
    steps.show_input,
    steps.indent,
    steps.start_time,
    steps.end_time

FROM
    steps

WHERE
    steps.id = $1
;
"""

SELECT_THREAD_STEPS_QUERY: str = """\
SELECT
    steps.id,
    steps.created,
    steps.thread_id,
    steps.parent_id,
    steps.type,
    steps.name,
    steps.streaming,
    steps.wait_for_answer,
    steps.is_error,
    steps.metadata,
    steps.tags,
    steps.input,
    steps.output,
    steps.generation,
    steps.show_input,
    steps.indent,
    steps.start_time,
    steps.end_time

FROM
    steps

WHERE
    steps.thread_id = $1

ORDER BY
    steps.created
;
"""

DELETE_THREAD_STEP_QUERY: str = """\
DELETE FROM
    steps

WHERE
    steps.id = $1
;
"""
