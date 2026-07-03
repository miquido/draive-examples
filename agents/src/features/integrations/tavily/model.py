from collections.abc import MutableSequence
from xml.sax.saxutils import escape  # nosec: B406

from draive import State

__all__ = ("ArticleRecord",)


class ArticleRecord(State):
    title: str
    url: str
    description: str = ""

    def render(self) -> str:
        entry: MutableSequence[str] = [
            "<article>",
            f"<title>{escape(self.title)}</title>",
            f"<url>{escape(self.url)}</url>",
        ]

        if self.description:
            entry.append(f"<description>{escape(self.description)}</description>")

        entry.append("</article>")
        return "".join(entry)
