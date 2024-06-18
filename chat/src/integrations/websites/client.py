from functools import partial
from http.cookiejar import CookieJar, DefaultCookiePolicy
from typing import Self
from urllib.parse import ParseResult, urlparse
from urllib.robotparser import RobotFileParser

from curl_cffi.requests import AsyncSession, Response  # pyright: ignore[reportMissingTypeStubs]
from draive import ScopeDependency

from integrations.websites.config import WebsiteScrapperConfig
from integrations.websites.content import HTMLContent
from integrations.websites.errors import WebsiteError

__all__ = [
    "WebsiteClient",
]


class WebsiteClient(ScopeDependency):
    @classmethod
    def prepare(cls) -> Self:
        return cls()

    def __init__(self) -> None:
        self._client: AsyncSession = AsyncSession(
            headers={"accept": "text/html"},
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

    async def request(
        self,
        website: str,
        *,
        query: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        follow_redirects: bool | None = None,
    ) -> HTMLContent:
        try:
            response: Response = await self._client.request(  # pyright: ignore[reportUnknownMemberType]
                method="GET",
                url=website,
                headers=headers,
                params=query,
                allow_redirects=follow_redirects,
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
                source=website,
                raw_content=response.content,
                encoding=response.encoding,
            )
        except Exception as exc:
            raise WebsiteError("Reading website content failed") from exc

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
            scrap_delay=crawl_delay,
            can_scrap=partial(parser.can_fetch, "*"),
        )
