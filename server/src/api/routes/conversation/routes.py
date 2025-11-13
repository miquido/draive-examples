from collections.abc import Sequence
from uuid import UUID

from draive import ConversationMessage, ObservabilityLevel, ctx
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.responses import JSONResponse, Response

from api.authorization import JWTAuthorizedAPIRoute
from features.conversation import thread_history, thread_prepare, thread_response_stream

__all__ = ("router",)

router = APIRouter(route_class=JWTAuthorizedAPIRoute)


@router.get(
    path="/conversation/prepare",
    description="Prepare a new conversation thread.",
    tags=["conversation"],
    status_code=200,
    responses={
        200: {
            "description": "Prepare a new conversation thread",
            "content": {"application/json": {"example": '{\n"thread_id": "UUID"\n}'}},
        },
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        500: {"description": "Internal server error"},
    },
)
async def prepare() -> Response:
    ctx.log_info("Preparing new conversation thread...")
    thread_id: UUID = await thread_prepare()
    ctx.record(
        ObservabilityLevel.INFO,
        metric="conversation.thread.created",
        value=1,
        kind="counter",
    )
    ctx.log_info("...conversation thread has been created!")
    return JSONResponse(
        status_code=200,
        content={
            "thread_id": str(thread_id),
        },
    )


class ConversationThreadRequest(BaseModel):
    message: str = Field(description="Content of the user message")


@router.post(
    path="/conversation/{thread_id}/respond",
    description="Respond to a message within conversation thread.",
    tags=["conversation"],
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Server-Sent Events stream of thread message response",
            "content": {
                "text/event-stream": {"example": "event: response\ndata: Hello World!\n\n"}
            },
        },
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        500: {"description": "Internal server error"},
    },
)
async def respond(
    thread_id: UUID,
    # request: Annotated[ConversationThreadRequest, Body(embed=False)],
    request: ConversationThreadRequest,
) -> StreamingResponse:
    ctx.log_info(f"...responding in thread ({thread_id})...")
    ctx.record(
        ObservabilityLevel.INFO,
        metric="conversation.thread.message",
        value=1,
        kind="counter",
        attributes={"thread_id": str(thread_id)},
    )

    return StreamingResponse(
        thread_response_stream(
            thread_id=thread_id,
            message=request.message,
        ),
        media_type="text/event-stream",
    )


@router.get(
    path="/conversation/{thread_id}",
    description="Access current messages within conversation thread.",
    tags=["conversation"],
    status_code=200,
    responses={
        200: {"description": "Access current messages within conversation thread"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        500: {"description": "Internal server error"},
    },
)
async def history(
    thread_id: UUID,
    limit: int = 1024,  # using high default limit to ensure complete history
) -> Response:
    ctx.log_info(f"Accessing thread ({thread_id}) history...")
    history: Sequence[ConversationMessage] = await thread_history(
        thread_id,
        limit=limit,
    )
    ctx.log_info(f"...thread ({thread_id}) history has been loaded!")
    return JSONResponse(
        status_code=200,
        content={
            "messages": [
                {
                    "role": element.role,
                    "content": element.content.to_str(),
                }
                for element in history
            ],
        },
    )
