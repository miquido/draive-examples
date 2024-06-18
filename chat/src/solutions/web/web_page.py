from asyncio import gather
from collections.abc import Sequence

from draive import (
    Argument,
    auto_retry,
    count_text_tokens,
    ctx,
    generate_text,
    split_sequence,
    split_text,
    tool,
)
from integrations.websites import WebsiteClient
from integrations.websites.content import HTMLContent

__all__ = [
    "web_page_content",
]


@tool(description="Access website content")
async def web_page_content(
    url: str = Argument(
        description="Web page URL",
    ),
    topic: str = Argument(
        description="Access topic to narrow the results, the more detailed the better",
        default_factory=str,
    ),
) -> str:
    """
    Tool accessing contents of given URL and preparing rephrase of its content.
    When topic is provided it searches for the information in that topic.
    Otherwise general summary is provided.
    """
    page_content: HTMLContent = await ctx.dependency(WebsiteClient).request(website=url)

    return await _web_page_content(
        topic=topic or "General summary",
        text=page_content.text,
    )


async def _web_page_content(
    topic: str,
    text: str,
) -> str:
    match split_text(
        text=text,
        part_size=3072,
        count_size=count_text_tokens,
    ):
        case [] | [""]:
            return "N/A"

        case [part]:
            return await _prepare(
                topic=topic,
                text=part,
            )

        case [*parts]:
            return await _prepare_merged(
                topic=topic,
                texts=parts,
            )


PREPARE_INSTRUCTION: str = """\
Your task is to provide an extensive rephrase of provided TEXT within given TOPIC.

REQUIREMENTS:
* keep all possible details in the result while avoiding repetitions
* use only information from provided TEXT
* answer N/A if provided TEXT does not contain required information
* provide only the result without any comments or additions
"""
PREPARE_INPUT_TEMPLATE: str = """\
TOPIC:
{topic}
TEXT:
{text}
"""


@auto_retry(limit=2, delay=lambda attempt: attempt * 0.16)
async def _prepare(
    topic: str,
    text: str,
) -> str:
    ctx.log_debug("...rephrasing...")
    return await generate_text(
        instruction=PREPARE_INSTRUCTION,
        input=PREPARE_INPUT_TEMPLATE.format(
            topic=topic,
            text=text,
        ),
    )


MERGE_PARTS_LIMIT: int = 2
MERGE_INSTRUCTION: str = """\
Your task is to merge given list of TEXTS into a single one focusing on provided TOPIC.

REQUIREMENTS:
* keep all possible details in the result while avoiding repetitions
* use only information from provided TEXTS
* answer N/A if provided TEXT does not contain required information
* provide only the result without any comments or additions
"""
MERGE_INPUT_TEMPLATE: str = """\
TOPIC:
{topic}
TEXTS:
{texts}
"""


@auto_retry(limit=2, delay=lambda attempt: attempt * 0.16)
async def _merge(
    topic: str,
    texts: Sequence[str],
) -> str:
    # Should keep merge list in limit
    assert len(texts) <= MERGE_PARTS_LIMIT  # nosec: B101
    match texts:
        case [result]:
            return result

        case [*results]:
            return await generate_text(
                instruction=MERGE_INSTRUCTION,
                input=MERGE_INPUT_TEMPLATE.format(
                    topic=topic,
                    texts="\n---\n".join(results),
                ),
            )


async def _prepare_merged(
    topic: str,
    texts: Sequence[str],
) -> str:
    results: list[str] = await gather(*[_prepare(topic=topic, text=text) for text in texts])
    while True:
        match await gather(
            *[
                _merge(topic=topic, texts=batch)
                for batch in split_sequence(
                    results,
                    part_size=MERGE_PARTS_LIMIT,
                )
            ]
        ):
            case [result]:
                return result

            case [*merged]:
                # Merge has to lower size of list
                assert len(results) > len(merged), f"{results}, {merged}"  # nosec: B101
                results = merged
