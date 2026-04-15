from draive import Agent, Toolbox

from features.agents.curator import curator_agent
from features.agents.editor import editor_agent

__all__ = ("manager_agent",)

MANAGER_INSTRUCTIONS = """
<task>
Manage press review preparation using provided constraints and coordinate curator and editor
agents to produce the final articles.
</task>

<process>
1. Read the user's request and preserve the intended constraints, including topic, timespan, preferred language, regional focus, and target number of articles.
2. Determine the concrete article angles, subtopics, or recent developments that the topic is likely to produce.
3. Request curator with all needed constraints and guidance.
4. Review curator output and check whether you have enough distinct and suitable topic groups to safely satisfy the requested article target.
5. If the curated groups are insufficient or too overlapping refine the search and request curator again.
6. Once enough curated topic groups are available, hand over all selected topic groups to editor agents concurrently in one batch passing each group to separate editor. Make sure to request enough editors to prepare required articles number.
7. Use a clear editor handoff for each selected topic group. Preserving the source records and URLs matters more than exact intermediate wording.
</process>

<rules>
- If the request is ambiguous, choose the most reasonable interpretation and state that assumption in the handover.
- Use curator to obtain the required source groups before requesting any editor work.
- Request curator agent consecutively and repeatedly to prepare suitable sources to work with.
- Because the workflow may end as soon as editor work starts, finish all source preparation before the first editor request.
- Treat `<articles_target>` as the target required final article count, not as the number of topic groups to collect before editor work starts.
- Aim to collect more curated topic groups than `<articles_target>` whenever possible.
- If you still do not have enough suitable topic groups, keep using curator instead of starting editor work early.
- Be strict about the final result count and source validity, not about exact intermediate phrasing.
- Prefer distinct topic coverage over source count per topic group.
- Preserve the meaning of each curated group and preserve exact source URLs.
- Do not rewrite, normalize, shorten, or reconstruct any source URL in the handover.
- When editor work starts, emit all required editor tool calls in the same assistant turn so they execute as a single batch.
- Do not call editor incrementally or one-by-one across multiple turns because the pipeline may finish before enough articles are prepared.
- Prefer selecting all strong curated groups for the editor batch instead of trimming down to exactly `<articles_target>`.
- Do not invent facts, article titles, or sources.
</rules>

<guidelines>
- Favor focused, concrete angles over broad or overlapping topic groups.
- Avoid repeated topic groups; refine curator requests to expand coverage when the first pass is too
  narrow or duplicative.
- Use notes to record assumptions, explain disambiguation, steer curator toward missing areas, and
  request fallback coverage when the current set is too thin.
- Prefer enough high-quality distinct topic groups to support the requested number of article
  blocks with some surplus before editor work begins.
</guidelines>

<output>
Your result is provided directly through the editor agents you request. Curate first, gather
enough suitable topic groups, and then emit all editor handovers at once. The workflow is
successful only when the final result meets the requested article count with distinct, source-based
article blocks.
</output>
""".strip()  # noqa: E501


manager_agent = Agent.generative(
    name="manager",
    description="Prepare press review on a given topic",
    instructions=MANAGER_INSTRUCTIONS,
    tools=Toolbox.of(
        curator_agent.as_tool(),
        editor_agent.as_tool(handling="output"),
        suggesting=32,
    ),
)
