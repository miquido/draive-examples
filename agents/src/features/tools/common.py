from collections.abc import MutableSequence, Sequence
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from xml.sax.saxutils import escape  # nosec: B406

from draive import State

__all__ = (
    "ArticleRecord",
    "published_datetime",
    "render_article",
    "render_news_error",
    "render_news_success",
)


class ArticleRecord(State):
    title: str
    url: str
    published_at: datetime
    source: str = ""
    description: str = ""


def published_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)

    try:
        published_at: datetime = parsedate_to_datetime(value.strip())
        if published_at.tzinfo is None:
            return published_at.replace(tzinfo=UTC)

        return published_at.astimezone(UTC)

    except (TypeError, ValueError, IndexError):
        return datetime.now(UTC)


def render_news_error(
    provider: str,
    *,
    message: str,
) -> str:
    return f'<news provider="{provider}" status="error">{message}</news>'


def render_article(article: ArticleRecord) -> str:
    entry: MutableSequence[str] = [
        "<article>",
        f"<title>{escape(article.title)}</title>",
        f"<url>{escape(article.url)}</url>",
        (
            f"<published_at>{article.published_at.date().isoformat()}</published_at>"
            if article.published_at
            else "<published_at>unknown</published_at>"
        ),
    ]

    if article.source:
        entry.append(f"<publisher>{escape(article.source)}</publisher>")

    if article.description:
        entry.append(f"<description>{escape(article.description)}</description>")

    entry.append("</article>")
    return "".join(entry)


def render_news_success(
    provider: str,
    *,
    articles: Sequence[ArticleRecord],
) -> str:
    return (
        f'<news provider="{provider}" status="ok">'
        f"{''.join(render_article(article) for article in articles)}"
        "</news>"
    )
