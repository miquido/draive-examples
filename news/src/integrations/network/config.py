from collections.abc import Callable

from draive import State

__all__ = [
    "WebsiteScrapperConfig",
]


class WebsiteScrapperConfig(State):
    website: str
    scrap_delay: float | None = None
    can_scrap: Callable[[str], bool] = lambda _: True
