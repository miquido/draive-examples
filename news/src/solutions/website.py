from draive import Argument, ctx, tool
from integrations.network import HTMLContent, NetworkClient

__all__ = [
    "read_website",
]


@tool(description="Read website content")
async def read_website(
    url: str = Argument(description="URL of the website to read"),
) -> str:
    ctx.log_debug("Requested content of %s", url)
    content: HTMLContent = await ctx.dependency(NetworkClient).request_html(url=url)
    return content.text
