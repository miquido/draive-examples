import json
from collections.abc import Mapping, MutableSequence
from datetime import UTC, datetime
from typing import Annotated, Any

from draive import BasicObject, HTTPClient, HTTPResponse, getenv_str, tool

from features.tools.common import ArticleRecord, render_news_error, render_news_success

__all__ = ("tavily_news_search",)


HTTP_ERROR_STATUS = 400
TAVILY_API_URL = "https://api.tavily.com/search"
DEFAULT_MAX_RESULTS = 10


def _published_datetime(value: str) -> datetime:
    if not value:
        return datetime.now(UTC)

    normalized: str = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"

    try:
        published_at = datetime.fromisoformat(normalized)

    except ValueError:
        return datetime.now(UTC)

    if published_at.tzinfo is None:
        return published_at.replace(tzinfo=UTC)

    return published_at.astimezone(UTC)


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


def _article_entry(
    item: BasicObject,
) -> ArticleRecord | None:
    url: str = str(item.get("url") or "").strip()
    if not url:
        return None

    title: str = str(item.get("title") or "").strip()
    description: str = str(item.get("content") or "").strip()
    source: str = str(item.get("source") or "").strip()
    published_at: datetime = _published_datetime(str(item.get("published_date") or ""))

    return ArticleRecord(
        title=title,
        url=url,
        published_at=published_at,
        source=source,
        description=description,
    )


@tool(
    description="Search recent news articles using Tavily Search API",
    handling="output",
)
async def tavily_news_search(
    topic: Annotated[str, "Topic to search"],
    days_back: Annotated[int, "Number of days to look back"] = 7,
    language: Annotated[str, "Preferred source language locale"] = "en-US",
    country: Annotated[str, "Preferred source country code"] = "US",
) -> str:
    usable_entries: MutableSequence[ArticleRecord] = []

    response: HTTPResponse
    try:
        response = await HTTPClient.post(
            url=TAVILY_API_URL,
            headers={"Content-Type": "application/json"},
            body=json.dumps(
                {
                    "api_key": getenv_str("TAVILY_API_KEY", required=True),
                    "query": _query(
                        topic.strip(),
                        language=language,
                        country=country,
                    ),
                    "topic": "news",
                    "days": max(days_back, 1),
                    "max_results": DEFAULT_MAX_RESULTS,
                    "include_raw_content": False,
                    "include_images": False,
                }
            ),
            follow_redirects=True,
        )

    except Exception as exc:
        return render_news_error(
            "tavily",
            message=f"Search request failed: {exc}",
        )

    if response.status_code >= HTTP_ERROR_STATUS:
        raise Exception(f"Tavily search failed with HTTP status {response.status_code}")

    try:
        payload_data: Mapping[str, Any] = json.loads((await response.body()).decode("utf-8"))

    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Exception(f"Tavily extract response could not be parsed: {exc}") from exc

    match payload_data:
        case {"results": [*results]}:
            for item in results:
                if entry := _article_entry(item):
                    usable_entries.append(entry)

        case _:
            raise Exception("Tavily search failed with no valid results")

    if not usable_entries:
        raise Exception("No news found for provided requirements")

    return render_news_success(
        "tavily",
        articles=usable_entries,
    )
