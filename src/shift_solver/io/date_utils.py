"""Shared date parsing utilities for I/O handlers."""

import logging
from datetime import date, datetime
from typing import Any, Literal

logger = logging.getLogger(__name__)

# Format strings for each date format option
DATE_FORMAT_STRINGS = {
    "iso": "%Y-%m-%d",  # 2026-01-15 (unambiguous)
    "us": "%m/%d/%Y",  # 01/15/2026
    "eu": "%d/%m/%Y",  # 15/01/2026
}

# All formats for auto mode (ISO first, then US, then EU)
ALL_FORMATS = [
    DATE_FORMAT_STRINGS["iso"],
    DATE_FORMAT_STRINGS["us"],
    DATE_FORMAT_STRINGS["eu"],
]

# Cache for tracking warned ambiguous dates to avoid duplicate warnings
_warned_dates: set[str] = set()


def _is_ambiguous_date(date_str: str) -> bool:
    """
    Check if a date string is ambiguous between US and EU formats.

    A date is ambiguous when both day and month values are <= 12,
    making it impossible to distinguish US (MM/DD/YYYY) from EU (DD/MM/YYYY).
    """
    if "/" not in date_str:
        return False

    parts = date_str.split("/")
    if len(parts) != 3:
        return False

    try:
        first = int(parts[0])
        second = int(parts[1])
        # Ambiguous if both could be month or day
        return 1 <= first <= 12 and 1 <= second <= 12 and first != second
    except ValueError:
        return False


def parse_date[E: Exception](
    value: Any,
    field_name: str,
    line_num: int,
    error_class: type[E],
    date_format: Literal["iso", "us", "eu", "auto"] = "auto",
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
        date_format: Date format to use:
            - "iso": Use YYYY-MM-DD only
            - "us": Use MM/DD/YYYY only
            - "eu": Use DD/MM/YYYY only
            - "auto": Try all formats, warn on ambiguous dates (default)

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

    # Determine which formats to try
    if date_format == "auto":
        formats_to_try = ALL_FORMATS
        # Warn about ambiguous dates in auto mode
        if _is_ambiguous_date(date_str) and date_str not in _warned_dates:
            _warned_dates.add(date_str)
            logger.warning(
                f"Ambiguous date '{date_str}' in {field_name} on line {line_num}. "
                f"Interpreting as US format (MM/DD/YYYY). "
                f"Set date_format config to 'eu' or 'iso' to avoid ambiguity."
            )
    else:
        formats_to_try = [DATE_FORMAT_STRINGS[date_format]]

    for fmt in formats_to_try:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue

    # Build helpful error message
    if date_format == "auto":
        format_help = "YYYY-MM-DD, MM/DD/YYYY, or DD/MM/YYYY"
    else:
        format_examples = {
            "iso": "YYYY-MM-DD",
            "us": "MM/DD/YYYY",
            "eu": "DD/MM/YYYY",
        }
        format_help = format_examples[date_format]

    raise error_class(
        f"Invalid date '{value}' for '{field_name}' on line {line_num}. "
        f"Expected format: {format_help}"
    )
