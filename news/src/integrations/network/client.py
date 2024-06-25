from collections.abc import Mapping
from functools import partial
from http.cookiejar import CookieJar, DefaultCookiePolicy
from io import BytesIO
from typing import Self
from urllib.parse import ParseResult, urlparse
from urllib.robotparser import RobotFileParser

from curl_cffi.requests import AsyncSession, Response  # pyright: ignore[reportMissingTypeStubs]
from draive import ScopeDependency

from integrations.network.config import WebsiteScrapperConfig
from integrations.network.content import HTMLContent, RSSContent
from integrations.network.errors import WebsiteError

__all__ = [
    "NetworkClient",
]


class NetworkClient(ScopeDependency):
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

    async def dispose(self) -> None:
        await self._client.close()

    async def request_headers(
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
            raise WebsiteError("Network request failed") from exc

        if response.status_code not in range(200, 300):
            raise WebsiteError(
                "Website responded with invalid status code  %d",
                response.status_code,
            )

        return response.headers

    async def request_html(
        self,
        url: str,
        *,
        query: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> HTMLContent:
        try:
            response: Response = await self._client.request(  # pyright: ignore[reportUnknownMemberType]
                method="GET",
                url=url,
                headers={**{"accept": "text/html"}, **(headers or {})},
                params=query,
                allow_redirects=True,
            )
        except Exception as exc:
            raise WebsiteError("Network request failed") from exc

        if response.status_code not in range(200, 300):
            raise WebsiteError(
                "Website responded with invalid status code  %d",
                response.status_code,
            )

        content_header: str = response.headers.get("content-type", "").lower()
        if "html" not in content_header:
            raise WebsiteError(
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
            raise WebsiteError("Reading website content failed") from exc

    async def request_rss(
        self,
        url: str,
        *,
        query: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> RSSContent:
        try:
            response: Response = await self._client.request(  # pyright: ignore[reportUnknownMemberType]
                method="GET",
                url=url,
                headers={**{"accept": "application/xml"}, **(headers or {})},
                params=query,
                allow_redirects=True,
            )
        except Exception as exc:
            raise WebsiteError("Network request failed") from exc

        if response.status_code not in range(200, 300):
            raise WebsiteError(
                "Website responded with invalid status code  %d",
                response.status_code,
            )
        content_header: str = response.headers.get("content-type", "").lower()
        if "xml" not in content_header:
            raise WebsiteError(
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
            raise WebsiteError("Reading website rss failed") from exc

    async def request_pdf(
        self,
        url: str,
        *,
        query: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> BytesIO:
        try:
            response: Response = await self._client.request(  # pyright: ignore[reportUnknownMemberType]
                method="GET",
                url=url,
                headers={**{"accept": "application/pdf"}, **(headers or {})},
                params=query,
                allow_redirects=True,
            )

        except Exception as exc:
            raise WebsiteError("Network request failed") from exc

        if response.status_code not in range(200, 300):
            raise WebsiteError(
                "Website responded with invalid status code  %d",
                response.status_code,
            )
        content_header: str = response.headers.get("content-type", "").lower()
        if "pdf" not in content_header:
            raise WebsiteError(
                "Website responded with invalid content type %s",
                content_header,
            )
        try:
            return BytesIO(response.content)

        except Exception as exc:
            raise WebsiteError("Reading pdf content failed") from exc

    async def scrapper_config(
        self,
        website: str,
        /,
    ) -> WebsiteScrapperConfig:
        website_url: ParseResult = urlparse(website)

        parser: RobotFileParser = RobotFileParser()
        response: Response = await self._client.request(  # pyright: ignore[reportUnknownMemberType]
            method="GET",
            url=f"{website_url.scheme}://{website_url.netloc}/robots.txt",
        )
        if response.status_code not in range(200, 300):
            raise WebsiteError(
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

        return WebsiteScrapperConfig(
            website=f"{website_url.scheme}://{website_url.netloc}",
            scrap_delay=crawl_delay,
            can_scrap=partial(parser.can_fetch, "*"),
        )
