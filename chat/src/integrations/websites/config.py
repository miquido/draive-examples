from collections.abc import Callable

from draive import State

__all__ = [
    "WebsiteScrappingConfig",
]


class WebsiteScrappingConfig(State):
    scrap_delay: float | None = None
    can_scrap: Callable[[str], bool] = lambda _: True
