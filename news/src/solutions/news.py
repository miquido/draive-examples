from asyncio import sleep
from urllib.parse import ParseResult, quote_plus, urlparse

from draive import Argument, ctx, frozenlist, tool

from integrations.network import Network, RSSArticle, RSSContent, WebsiteScrappingConfig

__all__ = [
    "explore_news",
]

COMMON_RSS_PATHS: frozenlist[str] = (
    "feed",
    "rss",
    "feed.xml",
    "rss.xml",
    "atom.xml",
    "index.xml",
)


@tool(description="Explore the news")
async def explore_news(
    topic: str = Argument(description="Topic of news search"),
    limit: int = Argument(description="Limit of articles to receive", default=16),
) -> list[RSSArticle]:
    ctx.log_debug("Requested news for %s", topic)
    client: Network = ctx.state(Network)
    # get the rss feed
    content: RSSContent = await client.scrap_rss(
        url=f"https://news.google.com/rss/search?q={quote_plus(topic)}"
    )
    # get the most recent on top
    sorted_articles: list[RSSArticle] = sorted(
        content.articles,
        key=lambda article: article.publication,
    )

    # look for articles allowed for robots
    selected_articles: list[RSSArticle] = []
    scrapper_configs: dict[str, WebsiteScrappingConfig] = {}
    for article in sorted_articles:
        parsed_url: ParseResult = urlparse(article.link)
        website: str = f"{parsed_url.scheme}://{parsed_url.netloc}"

        config: WebsiteScrappingConfig
        if current := scrapper_configs.get(website):
            config = current

            if delay := config.scrap_delay:
                await sleep(delay)
        else:
            config = await client.scrapping_config(article.link)
            scrapper_configs[website] = config

        # we should respect robots.txt however for example purposes
        # it is skipped to get any actual content without integrating
        # with additional 3rd party services
        #
        # if config.can_scrap(article.link):
        selected_articles.append(article)

        if len(selected_articles) >= limit:
            break  # limit the results - avoiding to overflow LLM context window

    ctx.log_debug(
        "News for %s provided %d results out of %d available",
        topic,
        len(selected_articles),
        len(sorted_articles),
    )

    return selected_articles
