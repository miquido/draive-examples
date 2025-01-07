from draive import (
    AgentMessage,
    AgentOutput,
    DataModel,
    Field,
    agent,
    ctx,
    frozenlist,
    generate_model,
)

from features.news.state import NewsArticleSource
from solutions.news import explore_news
from solutions.rss import read_rss

INSTRUCTION: str = """\
Your task is to find articles based on provided topic and guidelines.
Create a list of the articles made of URLs with brief descriptions based on \
provided sources.

When given article URLs as sources, use them as they are. \
Otherwise use given sources to read associated RSS feeds. \
If no sources were specified, explore relevant news yourself using the topic.

Do not make up articles that were not provided to you either directly or \
through a tool. When no relevant articles were found, return an empty list of articles.

Avoid duplicates and repetition, choose only one out of similar articles.

Provide only a single, raw JSON object according to the given schema:
```json
{schema}
```

No extra comments, tags or formatting should be included.
"""


class NewsSources(DataModel):
    articles: frozenlist[NewsArticleSource] = Field(
        description="List of news articles",
        default_factory=tuple,
    )


@agent(description="Looks for news sources")
async def sources(
    message: AgentMessage,
) -> AgentOutput:
    ctx.log_debug("Requested news sources")

    sources: NewsSources = await generate_model(
        NewsSources,
        instruction=INSTRUCTION,
        input=message.content,
        tools=[read_rss, explore_news],
        schema_injection="full",
    )

    return message.respond(
        "Here are the news sources",
        *sources.articles,
    )
