"""Shared date parsing utilities for I/O handlers."""

from datetime import date, datetime
from typing import Any

# Supported date formats for string parsing
DATE_FORMATS = [
    "%Y-%m-%d",  # ISO: 2026-01-15
    "%m/%d/%Y",  # US: 01/15/2026
    "%d/%m/%Y",  # EU: 15/01/2026
]


def parse_date[E: Exception](
    value: Any,
    field_name: str,
    line_num: int,
    error_class: type[E],
) -> date:
    """
    Parse a date from various input formats.

    Handles:
    - datetime objects (extracts date)
    - date objects (returns as-is)
    - Strings in supported formats (ISO, US, EU)

    Args:
        value: The value to parse (string, date, or datetime)
        field_name: Name of the field for error messages
        line_num: Line number for error messages
        error_class: Exception class to raise on errors

    Returns:
        Parsed date object

    Raises:
        error_class: If value is empty or cannot be parsed
    """
    if value is None:
        raise error_class(f"empty '{field_name}' on line {line_num}")

    # Handle datetime objects
    if isinstance(value, datetime):
        return value.date()

    # Handle date objects
    if isinstance(value, date):
        return value

    # Handle string values
    date_str = str(value).strip()
    if not date_str:
        raise error_class(f"empty '{field_name}' on line {line_num}")

    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue

    raise error_class(
        f"Invalid date '{value}' for '{field_name}' on line {line_num}. "
        f"Supported formats: YYYY-MM-DD, MM/DD/YYYY"
    )
