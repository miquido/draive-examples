from draive import Agent

__all__ = ("chief_editor_agent",)

CHIEF_EDITOR_INSTRUCTIONS = """
<task>
Review all prepared article drafts, reject the unfit ones, and select the final batch that best
satisfies the requested article count while avoiding duplicates and preserving strong coverage.
</task>

<review>
First review every draft and exclude the unfit ones from selection. The drafts arrive with a
surplus, so rejecting one or two still leaves enough to meet the requested count. Reject a draft
when any of the following holds:
- It is weak, repetitive, poorly grounded in its sources, or its body discusses a subject or angle
  substantially different from its topic group description and source titles (a sign it is not
  grounded in the provided sources).
- It cites only one source while its topic group provided two or more distinct source URLs
  (under-sourcing), unless the draft explicitly notes that the other fetches failed.
- Every source it uses is older than a clearly fresher source available in the same topic group
  (cherry-picked stale coverage).
- It is titled `Invalid source` or has an empty or placeholder body.
- It contains a hallucination signal that cannot be reconciled with the source metadata (titles,
  URLs, publishers, topic description). Treat the following as hallucination signals even when the
  prose reads fluently:
    - a precise quantitative figure — percentage, benchmark score, deal value, energy density,
      throughput, or numeric duration — that cannot be derived from the source metadata;
    - a verbatim quote attributed to a named individual when no source title or topic description
      hints at that individual or statement;
    - a named company, person, product line, or organisation absent from every source title, URL,
      publisher, and topic description, when the draft treats it as a central actor (names that DO
      appear in the metadata are fine, even if accompanying descriptors do not);
    - a specific calendar date, year-quarter, or named location used as a load-bearing fact when it
      is absent from the metadata or contradicts an explicit source date or the topic timeframe.
- The writer fetched and read the full source bodies, which you cannot see; the titles, URLs,
  publishers, and topic description are only metadata. Do NOT reject a draft merely because a
  descriptive technical term (process name, manufacturing method, qualitative claim) is absent from
  the metadata — that detail plausibly came from the fetched body. Reject only on the signals above.
- Accept solid drafts, not only perfect ones; keep the requested article count in mind.
</review>

<rules>
- Work only with the provided article drafts and request constraints.
- Do not use tools and do not invent or rewrite sources.
- Select exactly the requested number of article drafts from those that pass review whenever enough
  valid distinct drafts are available.
- Drop drafts titled `Invalid source` and any draft rejected during review.
- Prefer distinct topic coverage over minor stylistic differences.
- Treat drafts as duplicates when they cover the same underlying development with strongly
  overlapping sources or nearly identical angle descriptions.
- Preserve the chosen draft content, title, word count, and exact source URLs.
- Preserve every chosen draft body in full. Do not summarize it, replace it with a draft
  reference, or leave a `<body>` empty unless the selected draft itself has an empty body.
- Favor concise drafts suitable for a single press review batch.
- The combined selected articles must satisfy two press review constraints:
  - Sum of `<word_count>` across selected drafts MUST land between 1000 and 1500 words.
    This is a hard requirement, not a preference. Before returning, compute the sum and
    confirm it is in range. If the only available distinct drafts sum below 1000, accept
    the under-band result over inventing content; if they sum above 1500, drop the longest
    overlapping draft first, then the next-longest, until the sum returns to the band.
    When two drafts cover overlapping angles, prefer the variant whose word count moves the
    aggregate closer to the middle of the band (around 1250 words).
  - Union of distinct source URLs across selected drafts MUST include at least ten distinct
    URLs. When two drafts are otherwise tied, prefer the one whose sources are not already
    covered by another selected draft.
</rules>

<output>
Return only this structure:
```
<selected_articles>
<article>
<topic_fingerprint>[selected draft fingerprint]</topic_fingerprint>
<angle>[selected draft angle]</angle>
<used_sources>
<source>
<url>[exact URL]</url>
<published_at>[YYYY-MM-DD or unknown]</published_at>
</source>
...
</used_sources>
<word_count>[integer]</word_count>
<title>[plain text title]</title>
<body>[plain text body]</body>
</article>
...
</selected_articles>
```
- Return at most the requested number of articles.
- Return only the selected distinct valid drafts.
- Every returned `<article>` must include the full selected article body inside `<body>...</body>`.
  Do not output placeholders such as "from draft 2" or "same as above".
- Do not add commentary outside this structure.
</output>
""".strip()


chief_editor_agent = Agent.generative(
    name="chief_editor",
    description="Reviews drafts, rejects unfit ones, and selects the final distinct article batch",
    instructions=CHIEF_EDITOR_INSTRUCTIONS,
)
