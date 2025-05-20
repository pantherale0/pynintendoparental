"""Generic utilities."""

import inspect

def is_awaitable(func):
    """Check if a function is awaitable or not."""
    return inspect.iscoroutinefunction(func) or inspect.isasyncgenfunction(func)
