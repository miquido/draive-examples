import ipaddress
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlparse
from xml.sax.saxutils import escape  # nosec: B405 B406

from bs4 import BeautifulSoup, Tag
from draive import HTTPClient, HTTPResponse, getenv_str, tool

__all__ = ("web_content",)


@tool(description="Fetch a web page content")
async def web_content(
    url: str,
) -> str:
    if not _is_fetchable_url(url):
        return _render_result(
            url,
            status="error",
            content="Only public HTTP(S) article URLs are allowed",
        )

    response: HTTPResponse
    body: bytes
    try:
        response = await HTTPClient.get(
            url=url,
            headers=BROWSER_HEADERS,
            timeout=DEFAULT_REQUEST_TIMEOUT,
            follow_redirects=True,
        )

        if response.status_code >= HTTP_ERROR_STATUS:
            raise Exception(f"Invalid status code: {response.status_code}")

        body = await response.body()

    except Exception as exc:
        return await _render_with_tavily_fallback(
            url,
            message=f"Content access failed: {exc}",
        )

    try:
        _check_response_content(response, body=body)

    except Exception as exc:
        return await _render_with_tavily_fallback(
            url,
            message=f"Content access failed: {exc}",
        )

    soup: BeautifulSoup = _removing_noise(BeautifulSoup(body, "html.parser"))

    content: str = _extract_article_content(soup)
    if len(content) < MIN_CONTENT_TEXT_LENGTH:
        content = _extract_full_page_content(soup)

    if content:
        return _render_result(
            url,
            status="success",
            content=content,
        )

    else:
        return await _render_with_tavily_fallback(
            url,
            message="Page access succeeded but no usable page text was extracted",
        )


HTTP_ERROR_STATUS = 400
DEFAULT_REQUEST_TIMEOUT = 20.0
MAX_RESPONSE_BYTES = 2_000_000
MIN_CONTENT_TEXT_LENGTH = 200
RETRYABLE_HTTP_STATUSES = {401, 403, 406, 409, 429}
TAVILY_EXTRACT_URL = "https://api.tavily.com/extract"
BLOCKED_SELECTOR = ",".join(
    (
        "script",
        "style",
        "noscript",
        "template",
        "svg",
        "canvas",
        "iframe",
        "form",
        "nav",
        "footer",
        "aside",
        "header",
        "dialog",
        "[role='navigation']",
        "[role='complementary']",
        "[aria-modal='true']",
    )
)
NOISE_PATTERN = re.compile(
    r"(cookie|consent|subscribe|newsletter|related|recommend|share|social|"
    r"advert|ads?|promo|banner|breadcrumb|comment|outbrain|taboola|popup|modal|"
    r"sidebar|widget|top-news|filed-under|disclosure|author-box|social-share)",
    re.IGNORECASE,
)
CANDIDATE_SELECTORS = (
    "article",
    "main",
    "[role='main']",
    ".article",
    ".article-body",
    ".article-content",
    ".article__content",
    ".article-body-content",
    ".story-body",
    ".story-content",
    ".entry-content",
    ".post-content",
    ".post-body",
    ".main-content",
    ".ArticleBody",
    "[itemprop='articleBody']",
    "[data-testid='article-body']",
    "[data-component='text-block']",
)
WHITESPACE_PATTERN = re.compile(r"\n{3,}")
INLINE_WHITESPACE_PATTERN = re.compile(r"[^\S\n]+")
POST_ARTICLE_PATTERN = re.compile(
    r"\n(?:watch this video on youtube|browse through more resources|"
    r"filed under|disclosure:|primary sidebar|top news|guides|apple news|"
    r"android news|technology news)\b.*",
    re.IGNORECASE | re.DOTALL,
)
BLOCK_PAGE_PATTERN = re.compile(
    r"(access denied|forbidden|enable javascript|verify you are human|captcha|"
    r"attention required|request blocked|security check|cf-browser-verification|"
    r"please turn javascript on|bot detection)",
    re.IGNORECASE,
)

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/135.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
}

RETRY_HEADERS = {
    **BROWSER_HEADERS,
    "Accept-Language": "en-US,en;q=0.8",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}


def _normalized_plain_text(text: str) -> str:
    collapsed_inline = INLINE_WHITESPACE_PATTERN.sub(" ", text)
    return WHITESPACE_PATTERN.sub("\n\n", collapsed_inline).strip()


def _escape_attr(value: str) -> str:
    return escape(value, {'"': "&quot;"})


def _render_result(
    url: str,
    *,
    status: str,
    content: str,
) -> str:
    return f'<content url="{_escape_attr(url)}" status="{_escape_attr(status)}">{content}</content>'


def _is_blocked_hostname(hostname: str) -> bool:
    normalized: str = hostname.strip().lower().rstrip(".")
    if not normalized:
        return True

    if normalized == "localhost":
        return True

    if normalized.endswith((".local", ".internal")):
        return True

    try:
        address = ipaddress.ip_address(normalized)

    except ValueError:
        return False

    return bool(
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def _is_fetchable_url(url: str) -> bool:
    try:
        parsed_url = urlparse(url.strip())

    except Exception:
        return False

    return parsed_url.scheme.startswith("http") and not _is_blocked_hostname(
        parsed_url.hostname or ""
    )


def _normalized_text(tag: Tag) -> str:
    text: str = tag.get_text(separator="\n", strip=True)
    return _normalized_plain_text(text)


def _trim_post_article_sections(text: str) -> str:
    return POST_ARTICLE_PATTERN.sub("", text).strip()


def _is_noise(tag: Tag) -> bool:
    attr_value: str = " ".join(
        value if isinstance(value, str) else " ".join(value)
        for value in (tag.get("class"), tag.get("id"), tag.get("role"), tag.get("aria-label"))
        if value
    )
    return bool(attr_value and NOISE_PATTERN.search(attr_value))


def _removing_noise(soup: BeautifulSoup) -> BeautifulSoup:
    for blocked in soup.select(BLOCKED_SELECTOR):
        blocked.decompose()

    for tag in soup.find_all(_is_noise):
        tag.decompose()

    return soup


def _candidate_score(tag: Tag) -> tuple[float, int]:
    text: str = tag.get_text(separator=" ", strip=True)
    text_length: int = len(text)
    if text_length < MIN_CONTENT_TEXT_LENGTH:
        return (0.0, text_length)

    link_text_length: int = sum(
        len(link.get_text(separator=" ", strip=True)) for link in tag.find_all("a")
    )
    link_density: float = link_text_length / max(text_length, 1)
    paragraph_count: int = len(tag.find_all("p"))
    sentence_count: int = len(re.findall(r"[.!?]", text))
    heading_count: int = len(tag.find_all(re.compile(r"^h[1-6]$")))
    list_item_count: int = len(tag.find_all("li"))
    div_count: int = len(tag.find_all("div"))
    score: float = (
        text_length
        + paragraph_count * 120
        + sentence_count * 20
        - link_density * 1200
        - heading_count * 120
        - list_item_count * 18
        - max(div_count - paragraph_count * 2, 0) * 4
    )
    return (score, text_length)


def _extract_article_content(soup: BeautifulSoup) -> str:
    candidates: list[Tag] = []
    seen: set[int] = set()
    for selector in CANDIDATE_SELECTORS:
        for tag in soup.select(selector):
            if id(tag) not in seen:
                seen.add(id(tag))
                candidates.append(tag)

    if not candidates:
        return ""

    best = max(candidates, key=_candidate_score)
    score, _ = _candidate_score(best)
    if score <= 0:
        return ""

    return _trim_post_article_sections(_normalized_text(best))


def _extract_full_page_content(soup: BeautifulSoup) -> str:
    body = soup.body
    if body is not None:
        return _trim_post_article_sections(_normalized_text(body))

    return _trim_post_article_sections(_normalized_text(soup))


def _is_html_response(response: HTTPResponse) -> bool:
    content_type = (response.headers.get("content-type", "") or "").lower()
    if not content_type:
        return True

    return any(marker in content_type for marker in ("text/html", "application/xhtml+xml"))


def _looks_like_block_page(body: bytes) -> bool:
    sample = body[:50_000].decode("utf-8", errors="ignore")
    return bool(sample and BLOCK_PAGE_PATTERN.search(sample))


async def _fetch_tavily_content(url: str) -> str:
    response: HTTPResponse = await HTTPClient.post(
        url=TAVILY_EXTRACT_URL,
        headers={
            "Authorization": f"Bearer {getenv_str('TAVILY_API_KEY', required=True)}",
            "Content-Type": "application/json",
        },
        body=json.dumps(
            {
                "urls": [url],
                "extract_depth": "basic",
                "format": "text",
                "include_images": False,
                "include_favicon": False,
                "timeout": DEFAULT_REQUEST_TIMEOUT,
            }
        ),
        timeout=DEFAULT_REQUEST_TIMEOUT,
        follow_redirects=True,
    )

    if response.status_code >= HTTP_ERROR_STATUS:
        raise Exception(f"Tavily extract failed with HTTP status {response.status_code}")

    try:
        payload_data: Mapping[str, Any] = json.loads((await response.body()).decode("utf-8"))

    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Exception(f"Tavily extract response could not be parsed: {exc}") from exc

    return _parse_tavily_extract_payload(payload_data)


def _parse_tavily_extract_payload(payload_data: Mapping[str, Any]) -> str:
    match payload_data:
        case {"results": [*results]}:
            if content := _extract_tavily_result_content(results):
                return content

        case {"failed_results": [*results]}:
            raise Exception("Tavily extract failed")

        case _:
            pass

    raise Exception("Tavily extract returned no usable page text")


def _extract_tavily_result_content(results: Sequence[Any]) -> str:
    for item in results:
        match item:
            case {"raw_content": str() as raw_content}:
                if content := _trim_post_article_sections(_normalized_plain_text(raw_content)):
                    return content

            case _:
                continue

    return ""


async def _render_with_tavily_fallback(
    url: str,
    *,
    message: str,
) -> str:
    try:
        tavily_content = await _fetch_tavily_content(url)

    except Exception as exc:
        return _render_result(
            url,
            status="error",
            content=f"{message}; {exc}",
        )

    if tavily_content:
        return _render_result(
            url,
            status="success",
            content=tavily_content,
        )

    return _render_result(
        url,
        status="error",
        content=message,
    )


def _check_response_content(
    response: HTTPResponse,
    *,
    body: bytes,
) -> None:
    if response.status_code >= HTTP_ERROR_STATUS:
        raise Exception(f"Content access failed with HTTP status {response.status_code}")

    if not _is_html_response(response):
        raise Exception("Page access succeeded but the response was not HTML content")

    if not body:
        raise Exception("Page access succeeded but the response body was empty")

    if _looks_like_block_page(body):
        raise Exception("Page access was blocked by the publisher anti-bot protection")
