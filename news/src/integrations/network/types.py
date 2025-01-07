from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from integrations.network.config import WebsiteScrappingConfig
from integrations.network.content import HTMLContent, RSSContent

__all__ = [
    "HTMLScrapping",
    "HeadersScrapping",
    "NetworkError",
    "RSSScrapping",
    "WebsiteScrapperConfigAccessing",
]


@runtime_checkable
class HTMLScrapping(Protocol):
    async def __call__(
        self,
        url: str,
        *,
        query: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        follow_redirects: bool | None = None,
    ) -> HTMLContent: ...


@runtime_checkable
class RSSScrapping(Protocol):
    async def __call__(
        self,
        url: str,
        *,
        query: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        follow_redirects: bool | None = None,
    ) -> RSSContent: ...


@runtime_checkable
class HeadersScrapping(Protocol):
    async def __call__(
        self,
        url: str,
        *,
        query: dict[str, str] | None = None,
    ) -> Mapping[str, str]: ...


@runtime_checkable
class WebsiteScrapperConfigAccessing(Protocol):
    async def __call__(
        self,
        website: str,
        /,
    ) -> WebsiteScrappingConfig: ...


class NetworkError(Exception):
    pass
