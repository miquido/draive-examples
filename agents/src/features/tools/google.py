import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Annotated
from urllib.parse import parse_qs, unquote, urljoin, urlparse
from xml.etree import ElementTree  # nosec: B405

from draive import HTTPClient, HTTPResponse, tool

from features.tools.common import (
    ArticleRecord,
    published_datetime,
    render_news_error,
    render_news_success,
)

__all__ = ("google_news_search",)

HTTP_ERROR_STATUS = 400


def _redirect_target(value: str) -> str:
    if not value:
        return ""

    parsed = urlparse(value)
    query = parse_qs(parsed.query)
    target = query.get("url", [""])[0] or query.get("continue", [""])[0]
    if target:
        return unquote(target)

    return value


async def _resolved_link(value: str) -> str:
    resolved: str = _redirect_target(value)
    if not resolved:
        return ""

    current_url: str = resolved
    for _ in range(5):
        parsed = urlparse(current_url)
        if parsed.netloc != "news.google.com":
            return current_url

        try:
            response = await HTTPClient.get(
                url=current_url,
                headers={"User-Agent": "Mozilla/5.0"},
                follow_redirects=False,
            )

        except Exception:
            return ""

        location: str = _redirect_target(response.headers.get("location", ""))
        if response.status_code not in {301, 302, 303, 307, 308} or not location:
            return ""

        current_url = urljoin(current_url, location)

    return ""


async def _article_entry(
    item: ElementTree.Element,
    *,
    earliest_at: datetime | None,
) -> ArticleRecord | None:
    title: str = (item.findtext("title") or "").strip()
    if not title:
        return None

    link: str = await _resolved_link((item.findtext("link") or "").strip())
    if not link:
        return None

    publisher: str = (item.findtext("source") or "").strip()

    published_at: datetime = published_datetime((item.findtext("pubDate") or "").strip())
    if earliest_at is not None and published_at < earliest_at:
        return None

    description: str = (item.findtext("description") or "").strip()
    return ArticleRecord(
        title=title,
        url=link,
        published_at=published_at,
        source=publisher,
        description=description,
    )


@tool(
    description="Search recent news articles using Google News RSS",
    handling="output",
)
async def google_news_search(
    topic: Annotated[str, "Topic to search"],
    days_back: Annotated[int, "Number of days to look back"] = 7,
    language: Annotated[str, "BCP 47 language tag of sources"] = "en-US",
    country: Annotated[str, "ISO country code of sources"] = "US",
) -> str:
    query: str
    earliest_at: datetime | None = None
    if days_back > 0:
        query = f"{topic} when:{days_back}d"
        earliest_at = datetime.now(UTC) - timedelta(days=days_back)

    else:
        query = topic

    response: HTTPResponse
    try:
        response = await HTTPClient.get(
            url="https://news.google.com/rss/search",
            query={
                "q": query,
                "hl": language,
                "gl": country,
                "ceid": f"{country}:{language}",
            },
            follow_redirects=True,
        )

    except Exception as exc:
        return render_news_error(
            "google",
            message=f"Search request failed: {exc}",
        )

    if response.status_code >= HTTP_ERROR_STATUS:
        return render_news_error(
            "google",
            message=f"Search failed with HTTP status {response.status_code}"
            " for the provided requirements",
        )

    try:
        root = ElementTree.fromstring(await response.body())  # nosec: B314

    except ElementTree.ParseError as exc:
        return render_news_error(
            "google",
            message=f"RSS response could not be parsed: {exc}",
        )

    entries: Sequence[ArticleRecord | None] = await asyncio.gather(
        *(_article_entry(item, earliest_at=earliest_at) for item in root.findall("./channel/item"))
    )
    usable_entries = [entry for entry in entries if entry is not None]
    if not usable_entries:
        return render_news_error(
            "google",
            message="No news found for provided requirements",
        )

    return render_news_success(
        "google",
        articles=usable_entries,
    )
