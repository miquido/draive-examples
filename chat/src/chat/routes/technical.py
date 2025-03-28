from fastapi import APIRouter
from starlette.responses import Response

__all__ = [
    "router",
]

router = APIRouter()

@router.get(
    path="/health",
    description="Server health check with optional status and diagnostics.",
    status_code=204,
    responses={
        204: {"description": "Server up and running!"},
        500: {"description": "Internal server error"},
    },
)  # NOTE: this endpoint should be covered by nginx unit - it is used only in local builds
async def health() -> Response:
    return Response(status_code=204)
