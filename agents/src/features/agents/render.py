import re

__all__ = ("render_press_review",)

_FLAGS = re.DOTALL | re.IGNORECASE
_SELECTED_RE = re.compile(r"<selected_articles>(.*?)</selected_articles>", _FLAGS)
_ARTICLE_RE = re.compile(r"<article>(.*?)</article>", _FLAGS)
_TITLE_RE = re.compile(r"<title>(.*?)</title>", _FLAGS)
_BODY_RE = re.compile(r"<body>(.*?)</body>", _FLAGS)
_SOURCE_RE = re.compile(r"<source>(.*?)</source>", _FLAGS)
_URL_RE = re.compile(r"<url>(.*?)</url>", _FLAGS)
_PUBLISHED_AT_RE = re.compile(r"<published_at>(.*?)</published_at>", _FLAGS)

_SEPARATOR = "\n\n---\n\n"


def render_press_review(text: str) -> str:
    """Render chief_editor `<selected_articles>` XML into final markdown blocks.

    Invalid or empty-bodied articles are dropped. When multiple
    `<selected_articles>` blocks are present (e.g. the manager called
    chief_editor more than once), the last one is treated as the final
    selection. Returns an empty string when no valid article is found.
    """
    selected = _SELECTED_RE.findall(text)
    scope = selected[-1] if selected else text

    blocks: list[str] = []
    for raw in _ARTICLE_RE.findall(scope):
        title_match = _TITLE_RE.search(raw)
        body_match = _BODY_RE.search(raw)
        # Collapse to a single line and drop any leading markdown heading marks so
        # the rendered heading is always a clean `## <title>`.
        title = " ".join(title_match.group(1).split()).lstrip("#").strip() if title_match else ""
        body = body_match.group(1).strip() if body_match else ""
        if not title or title.casefold().startswith("invalid source") or not body:
            continue

        lines: list[str] = [f"## {title}"]
        for source in _SOURCE_RE.findall(raw):
            url_match = _URL_RE.search(source)
            url = url_match.group(1).strip() if url_match else ""
            if not url:
                continue

            published_match = _PUBLISHED_AT_RE.search(source)
            published = published_match.group(1).strip() if published_match else ""
            lines.append(f"- {published or 'unknown'} | {url}")

        lines.append("")
        lines.append(body)
        blocks.append("\n".join(lines))

    return _SEPARATOR.join(blocks)
