from draive import State

from integrations.websites.types import WebsiteScrapperConfigAccessing, WebsiteScrapping

__all__ = [
    "Websites",
]


class Websites(State):
    scrap: WebsiteScrapping
    scrapping_config: WebsiteScrapperConfigAccessing
