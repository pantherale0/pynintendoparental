"""Generic utilities."""

import inspect
from datetime import datetime
from zoneinfo import ZoneInfo


def is_awaitable(func):
    """Check if a function is awaitable or not."""
    return inspect.iscoroutinefunction(func) or inspect.isasyncgenfunction(func)


def current_datetime(tz: str) -> datetime:
    """Return the current time in the given IANA timezone."""
    return datetime.now(ZoneInfo(tz))
