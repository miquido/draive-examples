import json
from collections.abc import Mapping, Sequence
from typing import Any

from draive import (
    Instruction,
    InstructionDeclaration,
    Instructions,
    Meta,
    ctx,
)

from integrations.postgres import Postgres
from integrations.postgres.types import PostgresRow

__all__ = ("PostgresInstructionsRepository",)


def PostgresInstructionsRepository() -> Instructions:
    async def fetch_list(
        **extra: Any,
    ) -> Sequence[InstructionDeclaration]:
        try:
            return tuple(
                _decode_instruction_declaration(record)
                for record in await Postgres.fetch(
                    RECALL_DECLARATIONS_STATEMENT,
                )
            )

        except Exception as exc:
            ctx.log_error(
                "Failed to retrieve instructions from repository",
                exception=exc,
            )

            raise exc

    async def fetch(
        name: str,
        /,
        *,
        arguments: Mapping[str, str | float | int] | None = None,
        **extra: Any,
    ) -> Instruction | None:
        try:
            row: PostgresRow | None = await Postgres.fetch_one(
                RECALL_INSTRUCTION_STATEMENT,
                name,
            )
            if row is None:
                return None

            return _decode_instruction(
                row,
                arguments=arguments,
            )

        except Exception as exc:
            ctx.log_error(
                "Failed to retrieve instruction from repository",
                exception=exc,
            )

            raise exc

    return Instructions(
        list_fetching=fetch_list,
        fetching=fetch,
    )


def _decode_instruction(
    record: Mapping[str, Any],
    *,
    arguments: Mapping[str, str | float | int] | None,
) -> Instruction:
    return Instruction(
        name=record["name"],
        description=record["description"],
        content=record["content"],
        arguments=arguments if arguments is not None else {},
        meta=Meta.of(json.loads(record["meta"])),
    )


def _decode_instruction_declaration(
    record: Mapping[str, Any],
) -> InstructionDeclaration:
    return InstructionDeclaration(
        name=record["name"],
        description=record["description"],
        arguments=json.loads(record["arguments"]),
        meta=Meta.of(json.loads(record["meta"])),
    )


RECALL_INSTRUCTION_STATEMENT: str = """\
SELECT
    instructions.name,
    instructions.description,
    instructions.content,
    instructions.meta

FROM
    instructions

WHERE
    instructions.name = $1

LIMIT
    1
;\
"""

RECALL_DECLARATIONS_STATEMENT: str = """\
SELECT
    instructions.name,
    instructions.description,
    instructions.arguments,
    instructions.meta

FROM
    instructions
;\
"""
