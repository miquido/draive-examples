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

        # remove invalid sources
        # ## Invalid source
        result: str = "".join(accumulator)
        accumulator = []
        invalid: bool = False
        for line in result.split("\n"):
            if invalid:
                if line == "---":
                    invalid = False

                else:
                    continue

            elif line.startswith("## Invalid source"):
                invalid = True

            else:
                accumulator.append(line)

        print("\n".join(accumulator))


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
    default=os.environ.get("PRESS_REVIEW_MODEL", "gemini-3-flash-preview"),
    help=(
        "AI model to use for the workflow, for example gemini-3-pro. "
        "Defaults to PRESS_REVIEW_MODEL or gemini-3-flash-preview."
    ),
)
parser.add_argument(
    "--provider",
    type=str,
    default=os.environ.get("PRESS_REVIEW_MODEL_PROVIDER", "gemini"),
    help=(
        "AI model provider to use for the workflow, 'google' for gemini or 'openai'. "
        "Defaults to PRESS_REVIEW_MODEL_PROVIDER or gemini."
    ),
)
args = parser.parse_args()

if args.days_back < 1:
    parser.error("--days-back must be at least 1")

if args.articles_target < 1:
    parser.error("--articles-target must be at least 1")

run(
    prepare(
        subject=args.subject,
        days_back=args.days_back,
        language=args.language,
        country=args.country,
        articles_target=args.articles_target,
        model=args.model,
        provider=args.provider,
    )
)
