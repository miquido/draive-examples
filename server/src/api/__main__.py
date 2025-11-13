from granian.constants import Interfaces
from granian.server import Server

from api.config import SERVER_HOST, SERVER_PORT, SERVER_THREADS, SERVER_WORKERS

Server(
    "api.application:app",
    address=SERVER_HOST,
    port=SERVER_PORT,
    workers=SERVER_WORKERS,
    runtime_threads=SERVER_THREADS,
    interface=Interfaces.ASGI,
    reload=__debug__,
).serve()
