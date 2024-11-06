from collections.abc import Mapping
from functools import partial
from http.cookiejar import CookieJar, DefaultCookiePolicy
from typing import Self
from urllib.parse import ParseResult, urlparse
from urllib.robotparser import RobotFileParser

from curl_cffi.requests import AsyncSession, Response  # pyright: ignore[reportMissingTypeStubs]

from integrations.network.config import WebsiteScrappingConfig
from integrations.network.content import HTMLContent, RSSContent
from integrations.network.state import Network
from integrations.network.types import NetworkError

__all__ = [
    "NetworkClient",
]


class NetworkClient:
    @classmethod
    def prepare(cls) -> Self:
        return cls()

    def __init__(self) -> None:
        self._client: AsyncSession = AsyncSession(
            cookies=CookieJar(  # disable cookies
                policy=DefaultCookiePolicy(allowed_domains=[]),
            ),
            timeout=30,
            allow_redirects=False,
            impersonate="chrome",
            max_clients=32,
        )

    async def scrap_headers(
        self,
        url: str,
        *,
        query: dict[str, str] | None = None,
    ) -> Mapping[str, str]:
        try:
            response: Response = await self._client.request(  # pyright: ignore[reportUnknownMemberType]
                method="HEAD",
                url=url,
                params=query,
                allow_redirects=True,
            )

        except Exception as exc:
            raise NetworkError("Network request failed") from exc

        if response.status_code not in range(200, 300):
            raise NetworkError(
                "Website responded with invalid status code  %d",
                response.status_code,
            )

        return response.headers

    async def scrap_html(
        self,
        url: str,
        *,
        query: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        follow_redirects: bool | None = True,
    ) -> HTMLContent:
        try:
            response: Response = await self._client.request(  # pyright: ignore[reportUnknownMemberType]
                method="GET",
                url=url,
                headers={**{"accept": "text/html"}, **(headers or {})},
                params=query,
                allow_redirects=follow_redirects,
            )

        except Exception as exc:
            raise NetworkError("Network request failed") from exc

        if response.status_code not in range(200, 300):
            raise NetworkError(
                "Website responded with invalid status code  %d",
                response.status_code,
            )

        content_header: str = response.headers.get("content-type", "").lower()
        if "html" not in content_header:
            raise NetworkError(
                "Website responded with invalid content type %s",
                content_header,
            )

        try:
            return HTMLContent(
                source=url,
                raw_content=response.content,
                encoding=response.encoding,
            )

        except Exception as exc:
            raise NetworkError("Reading website content failed") from exc

    async def scrap_rss(
        self,
        url: str,
        *,
        query: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        follow_redirects: bool | None = True,
    ) -> RSSContent:
        try:
            response: Response = await self._client.request(  # pyright: ignore[reportUnknownMemberType]
                method="GET",
                url=url,
                headers={**{"accept": "application/xml"}, **(headers or {})},
                params=query,
                allow_redirects=follow_redirects,
            )

        except Exception as exc:
            raise NetworkError("Network request failed") from exc

        if response.status_code not in range(200, 300):
            raise NetworkError(
                "Website responded with invalid status code  %d",
                response.status_code,
            )

        content_header: str = response.headers.get("content-type", "").lower()
        if "xml" not in content_header:
            raise NetworkError(
                "Website responded with invalid content type %s",
                content_header,
            )
        try:
            return RSSContent(
                source=url,
                raw_content=response.content,
                encoding=response.encoding,
            )

        except Exception as exc:
            raise NetworkError("Reading website rss failed") from exc

    async def scrapping_config(
        self,
        website: str,
        /,
    ) -> WebsiteScrappingConfig:
        website_url: ParseResult = urlparse(website)

        parser: RobotFileParser = RobotFileParser()
        response: Response = await self._client.request(  # pyright: ignore[reportUnknownMemberType]
            method="GET",
            url=f"{website_url.scheme}://{website_url.netloc}/robots.txt",
        )
        if response.status_code not in range(200, 300):
            raise NetworkError(
                "Website responded with invalid status code  %d",
                response.status_code,
            )

        parser.parse(response.text.splitlines())

        crawl_delay: float | None
        if delay := parser.crawl_delay("*"):
            crawl_delay = float(delay)
        elif rate := parser.request_rate("*"):
            crawl_delay = float(rate.seconds)
        else:
            crawl_delay = None

        return WebsiteScrappingConfig(
            website=f"{website_url.scheme}://{website_url.netloc}",
            scrap_delay=crawl_delay,
            can_scrap=partial(parser.can_fetch, "*"),
        )

    async def initialize(self) -> Network:
        return Network(
            scrap_html=self.scrap_html,
            scrap_rss=self.scrap_rss,
            scrap_headers=self.scrap_headers,
            scrapping_config=self.scrapping_config,
        )

    async def dispose(self) -> None:
        await self._client.close()
