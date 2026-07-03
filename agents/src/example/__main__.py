import argparse
import os
from asyncio import run
from collections.abc import MutableSequence
from datetime import UTC, datetime

from draive import ctx, setup_logging
from draive.gemini import Gemini, GeminiConfig
from draive.httpx import HTTPXClient
from draive.openai import OpenAI, OpenAIResponsesConfig

from features.agents import manager_agent
from features.agents.render import render_press_review
from features.integrations.tavily import Tavily

setup_logging("agents")


async def prepare(  # noqa: PLR0913
    *,
    subject: str,
    days_back: int,
    language: str,
    country: str | None,
    articles_target: int,
    model: str,
    provider: str,
) -> None:
    async with ctx.scope(
        "preparation",
        GeminiConfig(model=model),
        OpenAIResponsesConfig(model=model),
        disposables=(
            OpenAI() if provider == "openai" else Gemini(),
            HTTPXClient(),
            Tavily(),
        ),
    ):
        ctx.log_info(f"Subject: {subject}")
        accumulator: MutableSequence[str] = []
        async for chunk in manager_agent.call(
            input=(
                "Prepare a press review on the following topic:"
                f"\n{subject}"
                "\n\nConstraints:\n"
                f"\n- Current date: {datetime.now(UTC).date().isoformat()}"
                f"\n- Focus on recent coverage from the last {days_back} days."
                f"\n- Preferred language locale: {language}."
                f"\n- Preferred regional focus: {country if country else 'global'}."
                f"\n- Articles target: {articles_target} distinct article blocks."
                "\n- Prefer sources matching the locale and region unless clearly relevant "
                "context requires otherwise."
            ),
        ):
            accumulator.append(chunk.to_str())

        # The manager streams chief_editor's <selected_articles> XML as its output;
        # render it into the final markdown article blocks deterministically.
        print(render_press_review("".join(accumulator)))


parser = argparse.ArgumentParser(description="Prepare press review")
parser.add_argument(
    "--subject",
    type=str,
    required=True,
    help="Subject for press review",
)
parser.add_argument(
    "--days-back",
    type=int,
    default=30,
    help="How many recent days of coverage to prioritize",
)
parser.add_argument(
    "--language",
    type=str,
    default="en-US",
    help="Preferred source language locale, for example en-US",
)
parser.add_argument(
    "--country",
    type=str,
    default=None,
    help="Preferred regional focus to pass to the manager",
)
parser.add_argument(
    "--articles-target",
    type=int,
    default=5,
    help="Target number of distinct final article blocks",
)
parser.add_argument(
    "--model",
    type=str,
    default=os.environ.get("PRESS_REVIEW_MODEL", "gpt-5-mini"),
    help=(
        "AI model to use for the workflow, for example gpt-5-mini. "
        "Defaults to PRESS_REVIEW_MODEL or gpt-5-mini."
    ),
)
parser.add_argument(
    "--provider",
    type=str,
    default=os.environ.get("PRESS_REVIEW_MODEL_PROVIDER", "openai"),
    help=(
        "AI model provider to use for the workflow, 'gemini' or 'openai'. "
        "Defaults to PRESS_REVIEW_MODEL_PROVIDER or gemini."
    ),
)
args = parser.parse_args()

if args.days_back < 1:
    parser.error("--days-back must be at least 1")

if args.articles_target < 1:
    parser.error("--articles-target must be at least 1")

provider = args.provider.lower()
if provider not in {"gemini", "openai"}:
    parser.error("--provider must be 'gemini' or 'openai'")

run(
    prepare(
        subject=args.subject,
        days_back=args.days_back,
        language=args.language,
        country=args.country,
        articles_target=args.articles_target,
        model=args.model,
        provider=provider,
    )
)
