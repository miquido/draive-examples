from contextlib import asynccontextmanager
from logging import Logger, getLogger

from draive import Disposables, setup_logging
from draive.openai import OpenAI, OpenAIChatConfig
from fastapi import FastAPI

from chat.frontend import setup_frontend
from chat.middlewares import ContextMiddleware
from chat.routes import technical_router
from integrations.postgres import PostgresConnectionPool, PostgresConnection

__all__ = [
    "app",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging("server")

    logger: Logger = getLogger("server")
    if __debug__:
        logger.warning("Starting DEBUG server...")

    else:
        logger.info("Starting server...")

    openai = OpenAI()
    disposables = Disposables(
        openai,
        PostgresConnectionPool(),
    )
    async with disposables as state:
        app.extra["state"] = (
            *state,
            openai.lmm_invoking(),
            openai.lmm_streaming(),
            openai.text_embedding(),
            openai.tokenizer("gpt-4o"),
            OpenAIChatConfig(model="gpt-4o"),
        )

        logger.info("...server started...")
        yield  # suspend until server shutdown

    logger.info("...server shutdown!")


app: FastAPI = FastAPI(
    title="ChainlitChat",
    description="ChainlitChat example",
    version="0.1.0",
    lifespan=lifespan,
    openapi_url="/openapi.json" if __debug__ else None,
    docs_url="/swagger" if __debug__ else None,
    redoc_url="/redoc" if __debug__ else None,
)

# middlewares
app.add_middleware(ContextMiddleware)

# routes
app.include_router(technical_router)

# chainlit
setup_frontend(app=app)
