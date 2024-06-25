from draive import Argument, frozenlist, tool

from features.news.state import NewsPage, NewsScratchpad, NewsTask
from features.news.workflow import news_workflow

__all__ = [
    "prepare_news",
]


def _format_result(page: NewsPage) -> str:
    return page.as_markdown()


@tool(
    description="Prepare a news page according to the requirements",
    format_result=_format_result,
    direct_result=True,
)
async def prepare_news(
    topic: str = Argument(
        description="Description of what should be contained in news",
    ),
    guidelines: str = Argument(
        description="Optional guidelines and notes for preparing news",
        default_factory=str,
    ),
    sources: frozenlist[str] = Argument(
        description="Optional list of websites and urls to use as sources",
        default_factory=tuple,
    ),
) -> NewsPage:
    return await news_workflow.run(
        input="Prepare a news page",
        state=NewsScratchpad(
            task=NewsTask(
                topic=topic,
                guidelines=guidelines,
                sources=sources,
            ),
        ),
        timeout=240,
    )
