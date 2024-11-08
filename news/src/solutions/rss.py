from asyncio import sleep
from collections.abc import Mapping
from urllib.parse import ParseResult, urlparse

from draive import Argument, ctx, frozenlist, tool

from integrations.network import Network, RSSArticle, RSSContent, WebsiteScrappingConfig

__all__ = [
    "read_rss",
]

COMMON_RSS_PATHS: frozenlist[str] = (
    "feed",
    "rss",
    "feed.xml",
    "rss.xml",
    "atom.xml",
    "index.xml",
)


@tool(description="Read rss feed")
async def read_rss(  # noqa: PLR0912
    url: str = Argument(description="URL of the website to read its rss feed"),
    limit: int = Argument(description="Limit of articles to receive", default=16),
) -> list[RSSArticle]:
    ctx.log_debug("Requested RSS for %s", url)
    client: Network = ctx.state(Network)
    rss_url: str
    # check provided url content
    headers: Mapping[str, str]
    try:
        headers = await client.scrap_headers(url=url)

    except Exception:
        headers = {}

    if "xml" in headers.get("content-type", "").lower():
        rss_url = url  # if we got rss from provided url use it

    else:  # if not xml found check common paths
        parsed_url: ParseResult = urlparse(url)
        base_url: str = f"{parsed_url.scheme}://{parsed_url.netloc}/"

        for path in COMMON_RSS_PATHS:
            candidate_url: str = base_url + path
            try:
                headers = await client.scrap_headers(url=candidate_url)

            except Exception:
                continue  # nosec: B112

            if "xml" in headers.get("content-type", "").lower():
                rss_url = candidate_url
                break  # use the first matching

            else:
                continue

        else:  # when no common url was matching return empty
            ctx.log_debug("RSS for %s was not available", url)
            return []

    # get the rss feed
    content: RSSContent = await client.scrap_rss(url=rss_url)
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
        "RSS for %s provided %d results out of %d available",
        url,
        len(selected_articles),
        len(sorted_articles),
    )

    return selected_articles
