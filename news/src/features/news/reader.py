from draive import (
    AgentMessage,
    AgentOutput,
    MultimodalContent,
    agent,
    ctx,
    generate_text,
)

from features.news.state import NewsArticleScratchpad, NewsArticleSource
from solutions.website import read_website

INSTRUCTION: str = """\
You are an AI assistant responsible for reading news articles and creating a detailed summary. \
Follow these steps:

1. Read all provided texts carefully. Focus on key information, main topics, important details, \
and any recurring themes.

2. Review the note requirements thoroughly to understand what needs to be addressed.

3. Create your article summary using the news articles and given requirements. Ensure you:
   - Address all points mentioned in the structure section.
   - Provide accurate and relevant information from the news articles.
   - Organize the information logically and coherently.
   - Use clear, plain, and concise language.

4. Structure your article summary as follows:
   - Start with a brief overview of the main topics covered in the news article.
   - Divide the note into sections based on the requirements or main themes.
   - Use bullet points or numbered lists to improve readability.
   - Include relevant quotes or statistics from the news articles, citing the source.

5. After preparing your note, review it to ensure:
   - All requirements are met.
   - The information is accurate and properly sourced.
   - The note is well-organized and easy to read.
   - There are no grammatical errors or typos.
   - The language is plain and clear.

Your goal is to provide a comprehensive content note based on the news articles and requirements \
given, without adding personal opinions or information from external sources.
"""


@agent(description="Reads the news when given sources and tells about its content")
async def reader(
    message: AgentMessage,
) -> AgentOutput:
    ctx.log_debug("Requested reader work")

    source: NewsArticleSource
    if sources := message.content.artifacts(NewsArticleSource):
        source = sources[0]

    else:
        # we could request sources agent here, but this example should be relatively simple
        return message.respond("I am not able to prepare an article without sources.")

    # prefetch the website content instead of using tools - we will use it anyways
    # if we fail to get the article content workflow will handle the error
    website_content: str = await read_website(url=source.url)
    content: str = await generate_text(
        instruction=INSTRUCTION,
        input=MultimodalContent.of(
            message.content,
            f"WebsiteContent:\n{website_content}",
        ),
    )

    return message.respond(
        "Here is the article content",
        NewsArticleScratchpad(
            url=source.url,
            description=source.description,
            content=content,
        ),
    )
