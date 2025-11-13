from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from logging import Logger, getLogger

from draive import Disposables, setup_logging
from draive.openai import OpenAI
from draive.postgres import (
    PostgresConfigurationRepository,
    PostgresConnectionPool,
    PostgresTemplatesRepository,
)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import VERSION
from api.middlewares import ContextMiddleware
from api.otel import setup_telemetry
from api.routes import conversation_router, technical_router
from solutions.jwt import LocalJWTVerification

__all__ = ("app",)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    setup_logging("api", disable_existing_loggers=False)

    logger: Logger = getLogger("api")
    if __debug__:
        logger.warning("Starting DEBUG api...")

    else:
        logger.info("Starting api...")

    disposables = Disposables.of(
        OpenAI(),
        PostgresConnectionPool(),
    )

    try:
        app.extra["state"] = (
            *await disposables.prepare(),
            LocalJWTVerification(),
            PostgresConfigurationRepository(),
            PostgresTemplatesRepository(),
        )
        app.extra["otel"] = setup_telemetry()
        logger.info("...api started...")
        yield  # suspend until server shutdown

    except BaseException as exc:
        logger.error(
            f"...api startup failed: {exc}... ",
            exc_info=exc,
        )
        raise exc

    finally:
        logger.info("...api shutting down...")
        await disposables.dispose()
        logger.info("...api closed!")


app = FastAPI(
    title="AI API",
    lifespan=lifespan,
    version=VERSION,
    openapi_url="/openapi.json" if __debug__ else None,
    docs_url="/swagger" if __debug__ else None,
    redoc_url="/redoc" if __debug__ else None,
)
# middlewares
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=("*",),
    allow_methods=("*",),
    allow_headers=("*",),
)
app.add_middleware(ContextMiddleware)
# routes
app.include_router(
    conversation_router,
    prefix="/api/v1",
)
app.include_router(technical_router)
