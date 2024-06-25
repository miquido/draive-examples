from draive import (
    AgentError,
    AgentWorkflowInput,
    AgentWorkflowOutput,
    Memory,
    ctx,
    workflow,
)

from features.news.editor import editor as editor_agent
from features.news.nodes import workflow_agent
from features.news.reader import reader as reader_agent
from features.news.sources import sources as sources_agent
from features.news.state import (
    NewsArticleScratchpad,
    NewsArticleSource,
    NewsPage,
    NewsScratchpad,
)


@workflow(workflow_agent, state=NewsScratchpad)
async def news_workflow(  # noqa: C901, PLR0912, PLR0911
    memory: Memory[NewsScratchpad, NewsScratchpad],
    input: AgentWorkflowInput,  # noqa: A002
) -> AgentWorkflowOutput[NewsPage]:
    current_state: NewsScratchpad = await memory.recall()

    if isinstance(input, AgentError):
        ctx.log_debug("Workflow encountered an error")
        if (  # when reader failed on article remove it from the list
            input.agent == reader_agent
            and (articles := input.message.content.artifacts(NewsArticleScratchpad))
        ):
            # skip failed articles and continue
            current_state = current_state.updated(
                articles=tuple(
                    article for article in current_state.articles if article.url != articles[0].url
                ),
            )
            await memory.remember(current_state)
            return None  # wait for more things to come

        else:
            # otherwise fail the workflow
            raise input

    # when we have the result use it as the final result
    if result := input.content.artifacts(NewsPage):
        ctx.log_debug("Workflow received the result")
        return result[0]

    # look for updated articles
    if articles := input.content.artifacts(NewsArticleScratchpad):
        ctx.log_debug("Workflow received articles %d articles", len(articles))
        updated_articles: list[NewsArticleScratchpad] = list(articles)
        for existing in current_state.articles:
            if any(existing.url == updated.url for updated in updated_articles):
                continue  # skip duplicates

            else:
                updated_articles.append(existing)

        current_state = current_state.updated(
            articles=tuple(updated_articles),
        )
        await memory.remember(current_state)

    # look for updated sources and prepare empty articles out of it
    if sources := input.content.artifacts(NewsArticleSource):
        ctx.log_debug("Workflow received sources list of %d sources", len(sources))
        current_state = current_state.updated(
            articles=[
                *current_state.articles,
                *[
                    NewsArticleScratchpad(
                        url=source.url,
                        description=source.description,
                        content=None,
                    )
                    for source in sources
                ],
            ]
        )
        await memory.remember(current_state)

    # check if we are working on any articles
    if not current_state.articles:
        ctx.log_debug("Workflow requested sources")
        if input.sender == sources_agent:
            return input.respond("Please try again with different sources")

        else:
            sources_string: str = "\n".join("- " + source for source in current_state.task.sources)
            # look for the sources if not
            return sources_agent.address(
                "Prepare a list of articles suitable for the news request:",
                f"topic:\n{current_state.task.topic}",
                f"guidelines:\n{current_state.task.guidelines or 'N/A'}",
                f"sources:\n{sources_string or 'N/A'}",
            )

    # check if we have sources but not the content
    elif all(article.content is None for article in current_state.articles):
        ctx.log_debug("Workflow requested articles")
        # request to write the content concurrently
        return tuple(
            reader_agent.address(
                "Prepare a news article according to the guidelines using given source",
                f"topic:\n{current_state.task.topic}",
                f"guidelines:\n{current_state.task.guidelines}",
                NewsArticleSource(
                    url=article.url,
                    description=article.description or "N/A",
                ),
            )
            for article in current_state.articles
        )

    # wait for completing to write all articles

    elif (
        incomplete := len(
            [article for article in current_state.articles if article.content is None]
        )
    ) and incomplete > 0:
        ctx.log_debug("Workflow is waiting for %d articles to complete", incomplete)
        return None  # wait for more

    # when we have everything in place request final editing
    else:
        ctx.log_debug("Workflow requested final editing")
        return editor_agent.address(
            "Prepare a news page out of the following resources:",
            current_state,
        )
