from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from draive import State, statemethod

from features.integrations.tavily.model import ArticleRecord

__all__ = (
    "TavilyExtracting",
    "TavilySearch",
    "TavilySearching",
)


@runtime_checkable
class TavilySearching(Protocol):
    async def __call__(
        self,
        *,
        topic: str,
        days_back: int,
        language: str,
        country: str,
    ) -> Sequence[ArticleRecord]: ...


@runtime_checkable
class TavilyExtracting(Protocol):
    async def __call__(
        self,
        *,
        url: str,
    ) -> str: ...


class TavilySearch(State):
    """Context-resolved access to the Tavily search and extract services.

    The accessor methods resolve the active ``TavilySearch`` instance from the
    current scope (provided by the ``Tavily`` disposable), so call sites use
    ``await TavilySearch.search(...)`` / ``await TavilySearch.extract(...)``
    without holding a reference to the client.
    """

    searching: TavilySearching
    extracting: TavilyExtracting

    @statemethod
    async def search(
        self,
        *,
        topic: str,
        days_back: int = 7,
        language: str = "en-US",
        country: str = "US",
    ) -> Sequence[ArticleRecord]:
        return await self.searching(
            topic=topic,
            days_back=days_back,
            language=language,
            country=country,
        )

    @statemethod
    async def extract(
        self,
        *,
        url: str,
    ) -> str:
        return await self.extracting(url=url)
