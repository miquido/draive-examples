from draive import Agent, Toolbox

from features.tools import web_content

__all__ = ("editor_agent",)

EDITOR_INSTRUCTIONS = """
<task>
Read the provided sources and write an article based on them.
</task>

<rules>
- Read all provided sources using `web_content` before writing.
- Prepare the article based solely on the provided sources content.
- Do not invent facts, sources, or details, never produce articles without valid sources.
- If any source conflict, is incomplete, or `web_content` fails to retrieve content, skip it but keep them in sources with 'unavailable' mark.
- Use all valid provided sources to produce a solid article block from that topic group.
- When no valid sources are available use "Invalid source" for article title and keep content empty.
</rules>

<output>
Valid article block must follow exactly this structure:
  ## <plain text title>
  - <YYYY-MM-DD or unknown> | <full source URL>
  - <YYYY-MM-DD or unknown> | <full source URL>

  <plain text content>
- The first line must be a level-2 Markdown heading with only the title.
- After the heading, include one or more bullet lines with publication date, `|`, and full source URL for only the successfully fetched sources you actually used.
- After the source bullets, include a blank line and then the article body.
- Do not add any extra text, labels, or commentary outside that structure.
- Ignore source records without a `<url>` value and do not echo curator XML in the response.
</output>
""".strip()  # noqa: E501

editor_agent = Agent.generative(
    name="editor",
    description="Turns findings and leads into a clear, structured article",
    instructions=EDITOR_INSTRUCTIONS,
    tools=Toolbox.of(
        web_content,
        suggesting=True,
    ),
)
