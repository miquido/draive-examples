from draive import load_env

load_env()  # load env first if needed

from chat.application import app

__all__ = [
    "app",
]
