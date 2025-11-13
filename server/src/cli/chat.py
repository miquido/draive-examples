import argparse
import asyncio
import sys
import traceback
from uuid import UUID

from haiway import ctx

from cli.client import APIClient, ResponseChunk

__all__ = ("run_cli",)


async def print_message(
    message: ResponseChunk,
) -> None:
    if message.type == "assistant":
        print(
            f"{message.content}",
            end="",
            flush=True,
        )

    elif message.type == "event":
        print(
            message.content,
            "\n",
            flush=True,
        )


async def chat_loop(thread_id: UUID) -> None:
    print(f"\nThread ID: {thread_id} (you can resume thread using `--thread` launch argument)")
    print("\nYou can now chat with the assistant. Type 'quit' to end the conversation.\n")

    while True:
        try:
            print("-You-")  # New line between messages

            user_input: str = input()

            if user_input.lower() == "quit":
                print("\nGoodbye!")
                sys.exit(0)

            if not user_input.strip():
                continue

            print("\n-Assistant-")  # New line between messages

            async for message in APIClient.send_message(
                thread_id=thread_id,
                text=user_input,
            ):
                await print_message(message)

            print("\n")  # New line at the end of stream

        except KeyboardInterrupt:
            print("\nGoodbye!")
            sys.exit(0)

        except Exception as exc:
            print(f"\nError: {exc}")
            traceback.print_exc()
            sys.exit(-1)


async def _run_cli(thread_id: UUID | None = None) -> None:
    async with ctx.scope("cli"):
        if not thread_id:
            thread_id = await APIClient.create_thread()

        await chat_loop(thread_id)


def run_cli() -> None:
    parser = argparse.ArgumentParser(
        description="Conversation CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--thread",
        type=str,
        help="Resume an existing thread by providing its ID",
    )

    args = parser.parse_args()

    thread_id = None
    if args.thread:
        try:
            thread_id = UUID(args.thread)

        except ValueError:
            print(f"Invalid thread ID format: {args.thread}")
            sys.exit(1)

    asyncio.run(_run_cli(thread_id))
