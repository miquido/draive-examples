from collections.abc import AsyncIterator
from typing import Literal
from uuid import UUID

from draive import State
from httpx import AsyncClient, Response

from cli.config import API_BASE_URL, API_TOKEN
from cli.jwt import generate_jwt_token

__all__ = (
    "APIClient",
    "ResponseChunk",
    "SessionInfo",
)


class SessionInfo(State):
    session_id: UUID


class ResponseChunk(State):
    type: Literal["assistant", "event"]
    content: str


class APIClient:
    @classmethod
    async def create_thread(cls) -> UUID:
        async with AsyncClient(
            base_url=API_BASE_URL,
            headers={"Authorization": f"Bearer {_get_auth_token()}"},
            timeout=60,
        ) as client:
            response: Response = await client.get("/api/v1/conversation/prepare")
            response.raise_for_status()

            return UUID(response.json()["thread_id"])

    @classmethod
    async def send_message(
        cls,
        thread_id: UUID,
        text: str,
    ) -> AsyncIterator[ResponseChunk]:
        async with AsyncClient(
            base_url=API_BASE_URL,
            headers={"Authorization": f"Bearer {_get_auth_token()}"},
            timeout=60,
        ) as client:
            async with client.stream(
                "POST",
                f"/api/v1/conversation/{thread_id}/respond",
                json={"message": text},
            ) as response:
                response.raise_for_status()

                buffer: str = ""
                async for chunk in response.aiter_text():
                    buffer += chunk

                    while "\n\n" in buffer:
                        event_end = buffer.find("\n\n")
                        event_data = buffer[:event_end]
                        buffer = buffer[event_end + 2 :]

                        if not event_data.strip():
                            continue

                        lines = event_data.strip().split("\n")
                        event_type: str | None = None
                        data_content: str = ""

                        for line in lines:
                            if line.startswith("event: "):
                                event_type = line[7:]

                            elif line.startswith("data: "):
                                data_content = line[6:]

                        if event_type == "response":
                            yield ResponseChunk(
                                type="assistant",
                                content=data_content.replace("\\n", "\n"),
                            )

                        elif event_type and data_content:
                            yield ResponseChunk(
                                type="event",
                                content=f"[EVENT {event_type}] {data_content}",
                            )


def _get_auth_token() -> str:
    if API_TOKEN:
        return API_TOKEN

    return generate_jwt_token()
