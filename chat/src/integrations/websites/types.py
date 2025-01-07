from typing import Protocol, runtime_checkable

from integrations.websites.config import WebsiteScrappingConfig
from integrations.websites.content import HTMLContent

__all__ = [
    "WebsiteError",
    "WebsiteScrapperConfigAccessing",
    "WebsiteScrapping",
]


@runtime_checkable
class WebsiteScrapping(Protocol):
    async def __call__(
        self,
        website: str,
        *,
        query: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        follow_redirects: bool | None = None,
    ) -> HTMLContent: ...


@runtime_checkable
class WebsiteScrapperConfigAccessing(Protocol):
    async def __call__(
        self,
        website: str,
        /,
    ) -> WebsiteScrappingConfig: ...


class WebsiteError(Exception):
    pass
