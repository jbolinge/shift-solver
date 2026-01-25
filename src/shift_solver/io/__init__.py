"""I/O module for shift-solver."""

from shift_solver.io.csv_loader import CSVLoader, CSVLoaderError
from shift_solver.io.excel_handler import ExcelExporter, ExcelHandlerError, ExcelLoader
from shift_solver.io.sample_generator import IndustryPreset, SampleGenerator

__all__ = [
    "CSVLoader",
    "CSVLoaderError",
    "ExcelLoader",
    "ExcelExporter",
    "ExcelHandlerError",
    "SampleGenerator",
    "IndustryPreset",
]

# Backwards compatibility: date_utils can be imported from io
from shift_solver.io.date_utils import DATE_FORMATS, parse_date

__all__ += ["DATE_FORMATS", "parse_date"]
