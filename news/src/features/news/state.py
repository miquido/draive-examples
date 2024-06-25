from collections.abc import Sequence

from draive import DataModel, Field, frozenlist

__all__ = [
    "NewsScratchpad",
    "NewsArticleScratchpad",
    "NewsPage",
    "NewsArticle",
    "NewsTask",
    "NewsArticleSource",
]


class NewsTask(DataModel):
    topic: str = ""
    guidelines: str = ""
    sources: frozenlist[str] = Field(default_factory=tuple)


class NewsArticleSource(DataModel):
    url: str = Field(description="Full URL of the article")
    description: str = Field(
        default_factory=str,
        description="Short description of the article contents",
    )


class NewsArticleScratchpad(DataModel):
    url: str
    description: str | None
    content: str | None


class NewsScratchpad(DataModel):
    task: NewsTask = Field(default_factory=NewsTask)
    articles: frozenlist[NewsArticleScratchpad] = Field(default_factory=tuple)


class NewsArticle(DataModel):
    url: str = Field(description="Full URL of the article")
    title: str = Field(description="Title of this article")
    content: str = Field(description="Content of this article")

    def as_markdown(self) -> str:
        return f"## [{self.title}]({self.url})\n\n{self.content}\n"


class NewsPage(DataModel):
    editorial: str = Field(description="Short editorial for the news page about the articles")
    articles: Sequence[NewsArticle] = Field(description="List of the news articles")

    def as_markdown(self) -> str:
        return (
            "\n\n---\n"
            + self.editorial
            + "\n"
            + "\n\n---\n\n".join(article.as_markdown() for article in self.articles)
            + "\n---\n"
        )
