from draive import Agent, Toolbox

from features.tools import tavily_news_search

__all__ = ("searcher_agent",)

SEARCHER_INSTRUCTIONS = """
<goal>
Search for recent news sources for the assigned task.
</goal>

<rules>
- Use `search_news` tool to find news sources.
- Provide all `search_news` arguments according to the task description.
- Preserve the requested topic, time range, language, and country as closely as the tool allows.
- If the topic is broad, prefer one focused search per concrete subtopic instead of one vague search.
- If search yields no results for the requested time window, try broadening the topic keywords\
before giving up.
- Run additional, focused searches using different keyword angles to broaden results, but do not\
exceed four searches total.
- Preserve all usable articles on requested topic returned by the tools unless they are URL duplicates.
- Provide exact, full URLs of all sources received `search_news` tool.
- If the tool fails or returns no usable results, say so clearly.
- Optimize for diverse raw material to form distinct topic groups.
</rules>

<output>
Return your findings using following structure:
```
<search_results>
<request>
<topic>[requested topic]</topic>
<days_back>[requested days back]</days_back>
<language>[requested language]</language>
<country>[requested country]</country>
</request>
<articles status="ok|error">
<article>
<title>[exact title]</title>
<url>[exact URL]</url>
<published_at>[exact timestamp or unknown]</published_at>
<publisher>[publisher or unknown]</publisher>
<description>[description if available]</description>
</article>
...
<error>[error text only when status="error"]</error>
</articles>
...
</search_results>
```
Do not add anything outside this structure.
</output>
""".strip()  # noqa: E501

searcher_agent = Agent.generative(
    name="searcher",
    description="Finds relevant leads and sources given the topic, locale and time period.",
    instructions=SEARCHER_INSTRUCTIONS,
    tools=Toolbox.of(
        tavily_news_search,
        suggesting=True,
    ),
)
