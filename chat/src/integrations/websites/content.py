from datetime import UTC, datetime
from functools import cached_property
from typing import Self, cast

from bs4 import BeautifulSoup, Tag
from draive import freeze

__all__ = [
    "HTMLContent",
    "HTMLContentPart",
]

# note on selectors: https://beautiful-soup-4.readthedocs.io/en/latest/index.html?highlight=selector#css-selectors
# supported selectors: https://facelessuser.github.io/soupsieve/


class HTMLContentPart:
    def __init__(
        self,
        content: Tag,
    ) -> None:
        self._content: Tag = content

        freeze(self)

    @property
    def tag(self) -> str:
        return self._content.name

    @property
    def id(self) -> str | None:
        return self._content.attrs.get("id")

    @property
    def classes(self) -> list[str]:
        return cast(list[str], self._content.attrs.get("class", []))

    @cached_property
    def text(self) -> str:
        return self._content.text.strip()

    def find(
        self,
        selector: str,
        /,
    ) -> list[Self]:
        return [self.__class__(content=element) for element in self._content.select(selector)]


class HTMLContent:
    def __init__(
        self,
        source: str,
        raw_content: bytes,
        encoding: str | None = None,
        last_update: datetime | None = None,
    ) -> None:
        self._source: str = source
        self._raw_content: bytes = raw_content
        self._page: BeautifulSoup = BeautifulSoup(
            markup=raw_content,
            features="html.parser",
            from_encoding=encoding,
        )
        self._last_update: datetime = last_update or datetime.now(UTC)

        freeze(self)

    def __str__(self) -> str:
        return f"[{self.last_update}] {self.source}"

    @property
    def source(self) -> str:
        return self._source

    @property
    def raw(self) -> bytes:
        return self._raw_content

    @property
    def last_update(self) -> datetime:
        return self._last_update

    @cached_property
    def text(self) -> str:
        return (
            self._page.find(name="main") or self._page.find(name="body") or self._page
        ).text.strip()

    def find(
        self,
        selector: str,
        /,
    ) -> list[HTMLContentPart]:
        return [HTMLContentPart(content=element) for element in self._page.select(selector)]

    def find_text(
        self,
        selector: str,
        /,
    ) -> list[str]:
        return [element.text.strip() for element in self._page.select(selector)]
