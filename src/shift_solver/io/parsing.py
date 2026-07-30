"""Shared cell-parsing helpers used by both the CSV and Excel loaders.

CSVLoader and ExcelLoader each read the same logical columns (worker
'attributes', request 'is_hard', ...) out of different physical formats (raw
CSV strings vs. openpyxl cell values), but the *parsing rules* for those
columns should be identical -- a worker or request loaded from a CSV file
must come out the same as the equivalent Excel file. Centralizing the
parsing here (rather than duplicating it per-loader) is what makes that
parity guaranteed rather than merely tested for.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from shift_solver.io.csv_loader import CSVLoader
    from shift_solver.io.excel_handler.loader import ExcelLoader

# Suffixes (case-insensitive) recognized as Excel workbooks by make_loader/
# is_excel_path. Everything else is treated as CSV.
EXCEL_SUFFIXES = frozenset({".xlsx", ".xls"})


def is_excel_path(file_path: Path) -> bool:
    """Return True if `file_path`'s suffix indicates an Excel workbook."""
    return file_path.suffix.lower() in EXCEL_SUFFIXES


def make_loader(
    file_path: Path, date_format: str = "auto"
) -> "CSVLoader | ExcelLoader":
    """Construct the loader appropriate for `file_path`'s suffix.

    .xlsx/.xls -> ExcelLoader, everything else -> CSVLoader. This centralizes
    the suffix dispatch previously duplicated (and CSV-only, so .xlsx paths
    died with a CSVLoaderError) across the generate/validate/import-data CLI
    commands. Imports are deferred to avoid a circular import: csv_loader.py
    and excel_handler/loader.py both import cell parsers from this module.

    Args:
        file_path: Path whose suffix determines the loader type.
        date_format: Forwarded to the constructed loader (see
            date_utils.parse_date's date_format parameter).

    Returns:
        A CSVLoader or ExcelLoader instance.
    """
    from shift_solver.io.csv_loader import CSVLoader
    from shift_solver.io.excel_handler.loader import ExcelLoader

    if is_excel_path(file_path):
        return ExcelLoader(date_format=date_format)
    return CSVLoader(date_format=date_format)


def parse_is_hard[E: Exception](
    value: Any,
    line_num: int,
    error_class: type[E],
) -> bool | None:
    """Parse an optional 'is_hard' cell value.

    Accepts true/false/yes/no/1/0 (case-insensitive). Empty/None means
    "unset" (None), letting the caller apply its own default.

    Args:
        value: Raw cell value (str from CSV, or str/bool/int/None from
            Excel).
        line_num: Line/row number, for error messages.
        error_class: Exception class to raise on an unrecognized value.

    Returns:
        True, False, or None if the cell was empty.

    Raises:
        error_class: If the value isn't a recognized true/false spelling.
    """
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    if text.lower() in ("true", "yes", "1"):
        return True
    if text.lower() in ("false", "no", "0"):
        return False

    raise error_class(
        f"Invalid is_hard value '{value}' on line {line_num}. "
        f"Must be true/false/yes/no/1/0 or empty."
    )


def parse_attributes[E: Exception](
    value: Any,
    line_num: int,
    error_class: type[E],
) -> dict[str, str]:
    """Parse the optional 'attributes' cell into a Worker.attributes dict.

    Format: semicolon-separated `key=value` pairs, e.g.
    ``"certification=icu;seniority=senior"``. Whitespace around each entry,
    key, and value is stripped. This is what makes
    ShiftType.required_attributes / the `skills` constraint reachable from
    CSV- or Excel-loaded workers at all.

    Args:
        value: Raw 'attributes' cell value (may be missing/empty/None).
        line_num: Line/row number, for error messages.
        error_class: Exception class to raise on malformed entries.

    Returns:
        dict of parsed key/value pairs (empty if the column is blank).

    Raises:
        error_class: If an entry isn't a well-formed 'key=value' pair
            (missing '=', or an empty key).
    """
    if value is None:
        return {}
    raw = str(value).strip()
    if not raw:
        return {}

    attributes: dict[str, str] = {}
    for entry in raw.split(";"):
        entry = entry.strip()
        if not entry:
            continue
        if "=" not in entry:
            raise error_class(
                f"Invalid attributes entry '{entry}' on line {line_num}. "
                "Expected semicolon-separated 'key=value' pairs, e.g. "
                "'certification=icu;seniority=senior'."
            )
        key, _, val = entry.partition("=")
        key = key.strip()
        val = val.strip()
        if not key:
            raise error_class(
                f"Invalid attributes entry '{entry}' on line {line_num}: "
                "empty key. Expected semicolon-separated 'key=value' "
                "pairs, e.g. 'certification=icu;seniority=senior'."
            )
        attributes[key] = val

    return attributes
