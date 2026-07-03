import json
from collections.abc import Mapping, MutableSequence, Sequence
from types import TracebackType
from typing import Any, Final, final

from draive import HTTPClient, HTTPResponse, ctx, getenv_str

from features.integrations.tavily.config import TavilyConfig
from features.integrations.tavily.model import ArticleRecord
from features.integrations.tavily.state import TavilySearch

__all__ = (
    "Tavily",
    "TavilyError",
)

_HTTP_ERROR_STATUS: Final[int] = 400


class TavilyError(Exception):
    """Raised when a Tavily API call fails or returns an unusable payload."""


@final
class Tavily:
    """Disposable Tavily integration.

    Reads ``TAVILY_API_KEY`` lazily at construction (overridable via ``api_key``)
    so importing modules that use Tavily never requires the key to be present.
    Within an entered scope it provides a ``TavilySearch`` state bound to its
    search and extract methods, which issue requests through the ambient
    ``HTTPClient``.
    """

    __slots__ = (
        "_api_key",
        "_config",
    )

    def __init__(
        self,
        *,
        api_key: str | None = None,
        config: TavilyConfig | None = None,
    ) -> None:
        self._api_key: str = api_key or getenv_str("TAVILY_API_KEY", required=True)
        self._config: TavilyConfig = config if config is not None else TavilyConfig()

    async def __aenter__(self) -> TavilySearch:
        return TavilySearch(
            searching=self._search,
            extracting=self._extract,
        )

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        pass

    async def _search(
        self,
        *,
        topic: str,
        days_back: int,
        language: str,
        country: str,
    ) -> Sequence[ArticleRecord]:
        response: HTTPResponse
        try:
            response = await HTTPClient.post(
                url=self._config.search_url,
                headers={"Content-Type": "application/json"},
                body=json.dumps(
                    {
                        "api_key": self._api_key,
                        "query": _query(
                            topic.strip(),
                            language=language,
                            country=country,
                        ),
                        "topic": self._config.search_topic,
                        "days": max(days_back, 1),
                        "max_results": self._config.max_results,
                        "include_raw_content": False,
                        "include_images": False,
                    }
                ),
                follow_redirects=True,
            )

        except Exception as exc:
            ctx.log_error(
                f"Tavily search failed with error: {exc}",
                exception=exc,
            )
            raise TavilyError(f"News search failed: {exc}") from exc

        if response.status_code >= _HTTP_ERROR_STATUS:
            ctx.log_error(f"Tavily search failed with HTTP status: {response.status_code}")
            raise TavilyError("News search failed")

        try:
            payload_data: Mapping[str, Any] = json.loads((await response.body()).decode("utf-8"))

        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            ctx.log_error(f"Tavily search failed with decoding error: {exc}")
            raise TavilyError("News search failed") from exc

        articles: MutableSequence[ArticleRecord] = []
        match payload_data:
            case {"results": [*results]}:
                for item in results:
                    url: str = str(item.get("url") or "").strip()
                    if not url:
                        continue

                    articles.append(
                        ArticleRecord(
                            url=url,
                            title=str(item.get("title") or "").strip(),
                            description=str(item.get("content") or "").strip(),
                        )
                    )

            case _:
                pass  # no results

        return articles

    async def _extract(
        self,
        *,
        url: str,
    ) -> str:
        response: HTTPResponse = await HTTPClient.post(
            url=self._config.extract_url,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            body=json.dumps(
                {
                    "urls": [url],
                    "extract_depth": self._config.extract_depth,
                    "format": "text",
                    "include_images": False,
                    "include_favicon": False,
                    "timeout": self._config.timeout,
                }
            ),
            timeout=self._config.timeout,
            follow_redirects=True,
        )

        if response.status_code >= _HTTP_ERROR_STATUS:
            raise TavilyError(f"Tavily extract failed with HTTP status {response.status_code}")

        try:
            payload_data: Mapping[str, Any] = json.loads((await response.body()).decode("utf-8"))

        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TavilyError(f"Tavily extract response could not be parsed: {exc}") from exc

        match payload_data:
            case {"results": [*results]}:
                for item in results:
                    match item:
                        case {"raw_content": str() as raw_content} if raw_content.strip():
                            return raw_content

                        case _:
                            continue

            case {"failed_results": [*_]}:
                raise TavilyError("Tavily extract failed")

            case _:
                pass

        raise TavilyError("Tavily extract returned no usable page text")


def _query(
    topic: str,
    *,
    language: str,
    country: str,
) -> str:
    hints: MutableSequence[str] = []

    language_hint: str = language.strip()
    if language_hint:
        hints.append(f"language: {language_hint}")

    country_hint: str = country.strip()
    if country_hint:
        hints.append(f"country: {country_hint}")

    if not hints:
        return topic

    return f"{topic} ({', '.join(hints)})"
