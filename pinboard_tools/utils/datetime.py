# ABOUTME: Date and time utility functions for Pinboard data
# ABOUTME: Handles conversion between Pinboard and Python datetime formats

from datetime import UTC, datetime


def parse_pinboard_time(time_str: str) -> datetime:
    """Convert Pinboard time format to Python datetime

    Pinboard uses ISO format with 'Z' suffix for UTC
    """
    if time_str.endswith("Z"):
        time_str = time_str[:-1] + "+00:00"
    return datetime.fromisoformat(time_str)


def format_pinboard_time(dt: datetime) -> str:
    """Convert Python datetime to Pinboard time format"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_boolean(value: str | bool | int) -> bool:
    """Convert various boolean representations to Python bool

    Handles 'yes'/'no', True/False, 1/0
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    if isinstance(value, str):
        return value.lower() in ("yes", "true", "1")
    return False


def format_boolean_for_pinboard(value: bool) -> str:
    """Convert Python bool to Pinboard format ('yes'/'no')"""
    return "yes" if value else "no"
