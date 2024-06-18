from datetime import UTC, datetime

from draive import tool

__all__ = [
    "utc_datetime",
]


@tool(description="UTC date and time now")
async def utc_datetime() -> str:
    """
    Simple tool returning UTC datetime as string
    """
    return datetime.now(UTC).strftime("%A %d %B %Y, %H:%M:%S+%Z")
