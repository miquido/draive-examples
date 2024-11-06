from draive import State

from integrations.network.types import (
    HeadersScrapping,
    HTMLScrapping,
    RSSScrapping,
    WebsiteScrapperConfigAccessing,
)

__all__ = [
    "Network",
]


class Network(State):
    scrap_html: HTMLScrapping
    scrap_rss: RSSScrapping
    scrap_headers: HeadersScrapping
    scrapping_config: WebsiteScrapperConfigAccessing
