from draive import Agent, Toolbox

from features.tools import tavily_news_search

__all__ = ("searcher_agent",)

SEARCHER_INSTRUCTIONS = """
<task>
Search for recent news sources for the assigned topic.
</task>

<rules>
- Expect the curator handoff to clearly provide topic, time range, language, country, and search
  angles. The XML-like structure is preferred for clarity, but it is not mandatory.
- Use `tavily_news_search` to find news sources.
- Preserve the requested topic, time range, language, and country as closely as the tool allows.
- If the topic is broad, run a few focused searches instead of one vague search.
- If coverage is thin, broaden into adjacent concrete angles rather than stopping after the first
  weak search.
- Preserve all usable articles returned by the tools unless they are exact URL duplicates.
- Prefer returning exact URLs from tool output and note clearly when the tool returns no usable results.
- If the tool fails or returns no usable results, say so clearly.
- Optimize for giving curator enough diverse raw material to form distinct topic groups.
</rules>

<output>
Return only search findings using this structure:
```
<search_results>
<request>
<topic>[requested topic]</topic>
<days_back>[requested days back]</days_back>
<language>[requested language]</language>
<country>[requested country]</country>
</request>
<provider name="tavily" status="ok|error">
<articles>
<article>
<title>[exact title]</title>
<url>[exact URL]</url>
<published_at>[exact timestamp or unknown]</published_at>
<publisher>[publisher or unknown]</publisher>
<description>[description if available]</description>
</article>
...
</articles>
<error>[error text only when status="error"]</error>
</provider>
...
</search_results>
```
- Preserve URLs exactly as returned by the tool output.
- Preserve provider-level errors instead of replacing them with narrative summaries.
- Do not add commentary outside this structure.
</output>
""".strip()  # noqa: E501

searcher_agent = Agent.generative(
    name="searcher",
    description="Finds relevant leads and sources",
    instructions=SEARCHER_INSTRUCTIONS,
    tools=Toolbox.of(
        tavily_news_search,
        suggesting=True,
    ),
)
