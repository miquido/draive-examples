import re
from collections.abc import Sequence

from draive import (
    Agent,
    ModelContext,
    ModelInput,
    MultimodalContent,
    Step,
    StepState,
    execute_concurrently,
)

from features.tools import fetch_web_content

__all__ = ("writer_agent",)

WRITER_INSTRUCTIONS = """
<goal>
Prepare an article in requested topic, grounded in available sources.
</goal>

<context>
Sources have already been fetched for you and their contents are provided in a `<fetched_sources>`\
 block, where each `<content url="...">...</content>` entry holds the extracted source content.
Only successfully fetched sources appear there; failed fetches are omitted, so the block may hold\
 fewer sources than the topic listed, or be empty.
</context>

<process>
- Read the requested topic, its source metadata, and the fetched source content.
- Prepare one concise article on the requested topic, based solely on the fetched source content.
</process>

<rules>
- Use only the fetched source content. Every claim, figure, statistic, quote, name and date in the\
 article MUST appear in that content.
- Never invent, infer or extrapolate. Do not add background, context or detail that the fetched\
 sources do not state, even when it seems plausible or well-known.
- Cite every source whose content you actually used. When two or more sources were fetched\
 successfully, use and cite at least two of them.
- Preserve exact URLs for all used sources. Copy each `<published_at>` value verbatim from the\
 topic's source metadata; never reformat, change the year, or read a date off the page body.
- Target ~300 words of body content, unless the request specifies a different word budget.
- If `<fetched_sources>` contains no usable source content, do not write an article: return a\
 single article whose `<title>` is exactly `Invalid source` and whose `<body>` is empty.
</rules>

<output>
Return your article using the following structure:
```
<article>
<used_sources>
<source>
<url>[exact URL]</url>
<published_at>[YYYY-MM-DD or unknown]</published_at>
</source>
...
</used_sources>
<title>[plain text title]</title>
<body>[plain text body]</body>
</article>
```
Do not add anything outside this structure.
</output>
""".strip()

# Number of referenced sources fetched up front. Fetching runs concurrently, so the wall-clock cost
# is a single round-trip regardless of count; the cap bounds load while leaving a cushion above the
# two-source minimum in case some fetches fail.
_MAX_PREFETCHED_SOURCES = 5
_URL_RE = re.compile(r"<url>\s*(https?://\S+?)\s*</url>", re.IGNORECASE)
# fetch_web_content tags each block with status="success|error"; only successful ones are usable.
_SUCCESS_RE = re.compile(r'<content\b[^>]*\bstatus="success"', re.IGNORECASE)
# Marker appended by _prefetch_sources only when at least one source fetched successfully.
_FETCHED_SOURCES_MARKER = "<fetched_sources>"

# Emitted verbatim (no LLM call) when prefetching yields no usable source content. Mirrors the
# writer's documented "Invalid source" article so downstream selection (chief_editor) and rendering
# drop it on the same path as an LLM-produced invalid draft.
_INVALID_SOURCE_ARTICLE = """
<article>
<used_sources>
</used_sources>
<title>Invalid source</title>
<body></body>
</article>
""".strip()


async def _prefetch_sources(context: ModelContext) -> ModelContext:
    referenced_text: str = "\n".join(
        element.content.to_str() for element in context if isinstance(element, ModelInput)
    )

    # de-duplicate while preserving the curated order
    urls: list[str] = []
    for url in _URL_RE.findall(referenced_text):
        if url not in urls:
            urls.append(url)

    if not urls:
        return context

    fetched: Sequence[str] = await execute_concurrently(
        fetch_web_content,
        urls[:_MAX_PREFETCHED_SOURCES],
        concurrent_tasks=_MAX_PREFETCHED_SOURCES,
    )

    # Drop sources that failed to fetch so the writer never sees error placeholders.
    valid: list[str] = [block for block in fetched if _SUCCESS_RE.search(block)]

    if not valid:
        return context

    return (
        *context,
        ModelInput.of(
            MultimodalContent.of("<fetched_sources>\n" + "\n".join(valid) + "\n</fetched_sources>")
        ),
    )


async def _has_fetched_sources(state: StepState) -> bool:
    # _prefetch_sources appends the marker block only when a source fetched successfully; its
    # absence means there is nothing to ground an article in, so the LLM call must be skipped.
    last = state.context[-1]
    return isinstance(last, ModelInput) and _FETCHED_SOURCES_MARKER in last.content.to_str()


writer_agent = Agent.steps(
    Step.mutating_context(_prefetch_sources),
    Step.generating_completion(instructions=WRITER_INSTRUCTIONS).with_condition(
        _has_fetched_sources,
        # No usable sources: respond deterministically with an invalid-source draft instead of
        # asking the model to write one (which it cannot ground and might hallucinate).
        alternative=Step.appending_output(_INVALID_SOURCE_ARTICLE, emitting=True),
    ),
    name="writer",
    description="Fetches sources and prepares a structured article draft",
)
