from datetime import UTC, datetime

from draive import tool

__all__ = [
    "utc_datetime",
]


@tool(description="UTC time and date now")
async def utc_datetime() -> str:
    return datetime.now(UTC).strftime("%A %d %B, %Y, %H:%M:%S")
