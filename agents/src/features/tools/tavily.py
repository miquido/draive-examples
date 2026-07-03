from collections.abc import Sequence
from typing import Annotated

from draive import ctx, tool

from features.integrations.tavily import TavilyError, TavilySearch
from features.tools.common import ArticleRecord

__all__ = ("tavily_news_search",)


@tool(
    name="search_news",
    description="Search recent news articles",
    handling="output",
)
async def tavily_news_search(
    topic: Annotated[str, "Topic to search"],
    days_back: Annotated[int, "Number of days to look back"] = 7,
    language: Annotated[str, "Preferred source language locale"] = "en-US",
    country: Annotated[str, "Preferred source country code"] = "US",
) -> str:
    articles: Sequence[ArticleRecord]
    try:
        articles = await TavilySearch.search(
            topic=topic,
            days_back=days_back,
            language=language,
            country=country,
        )

    except TavilyError as exc:
        return f'<news status="error">{exc}</news>'

    if not articles:
        ctx.log_error("Tavily search provided no valid results")
        return '<news status="ok">News search provided no results for requested parameters</news>'

    return f'<news status="success">{"\n".join(article.render() for article in articles)}</news>'
