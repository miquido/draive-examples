from typing import Literal

from draive import Configuration

__all__ = ("TavilyConfig",)


class TavilyConfig(Configuration):
    """Tunable parameters for the Tavily integration.

    Carries the endpoint URLs and request shaping options shared by the
    search and extract calls. Defaults match Tavily's public API; override
    per scope by passing a configured instance to ``Tavily(...)``.
    """

    search_url: str = "https://api.tavily.com/search"
    extract_url: str = "https://api.tavily.com/extract"
    max_results: int = 30
    search_topic: Literal["general", "news"] = "news"
    extract_depth: Literal["basic", "advanced"] = "basic"
    timeout: float = 20.0
