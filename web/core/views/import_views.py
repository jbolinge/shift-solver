"""Data import views for CSV/Excel file upload."""

import tempfile
from pathlib import Path
from typing import Any

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from core.models import Worker


def _is_htmx(request: HttpRequest) -> bool:
    """Check if the request was made via HTMX."""
    return request.headers.get("HX-Request") == "true"


def import_page(request: HttpRequest) -> HttpResponse:
    """Display the import page with file upload form."""
    return render(request, "io/import_page.html")


def import_upload(request: HttpRequest) -> HttpResponse:
    """Handle file upload and show preview of parsed data."""
    if request.method != "POST":
        return render(request, "io/import_page.html")

    uploaded_file = request.FILES.get("file")
    data_type = request.POST.get("data_type", "workers")

    if not uploaded_file:
        return render(
            request,
            "io/import_page.html",
            {"errors": ["No file uploaded."]},
        )

    filename = uploaded_file.name or ""
    ext = Path(filename).suffix.lower()

    if ext not in (".csv", ".xlsx"):
        return render(
            request,
            "io/import_page.html",
            {"errors": ["Unsupported file type. Please upload a CSV or Excel file."]},
        )

    # Save to temp file for parsing
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        for chunk in uploaded_file.chunks():
            tmp.write(chunk)
        tmp_path = Path(tmp.name)

    try:
        parsed_rows = _parse_file(tmp_path, ext, data_type)
    except Exception as e:
        return render(
            request,
            "io/import_page.html",
            {"errors": [f"Error parsing file: {e}"]},
        )
    finally:
        tmp_path.unlink(missing_ok=True)

    # Store parsed data in session for confirmation step
    request.session["import_data"] = parsed_rows
    request.session["import_data_type"] = data_type

    template = "io/import_preview.html"
    context = {
        "rows": parsed_rows,
        "data_type": data_type,
        "count": len(parsed_rows),
    }
    if _is_htmx(request):
        return render(request, template, context)
    return render(request, template, context)


def import_confirm(request: HttpRequest) -> HttpResponse:
    """Confirm and execute the import from session-stored data."""
    if request.method != "POST":
        return render(request, "io/import_page.html")

    data_type = request.session.get("import_data_type", "workers")
    parsed_rows = request.session.get("import_data", [])

    if not parsed_rows:
        return render(
            request,
            "io/import_page.html",
            {"errors": ["No data to import. Please upload a file first."]},
        )

    created_count = 0
    skipped_count = 0

    if data_type == "workers":
        created_count, skipped_count = _import_workers(parsed_rows)

    # Clear session data
    request.session.pop("import_data", None)
    request.session.pop("import_data_type", None)

    return render(
        request,
        "io/import_page.html",
        {
            "success": True,
            "created_count": created_count,
            "skipped_count": skipped_count,
            "data_type": data_type,
        },
    )


def _parse_file(
    file_path: Path, ext: str, data_type: str
) -> list[dict[str, Any]]:
    """Parse uploaded file into list of row dicts."""
    if data_type == "workers":
        if ext == ".csv":
            from shift_solver.io import CSVLoader

            loader = CSVLoader()
            workers = loader.load_workers(file_path)
            return [
                {
                    "id": w.id,
                    "name": w.name,
                    "worker_type": w.worker_type or "",
                }
                for w in workers
            ]
        elif ext == ".xlsx":
            from shift_solver.io import ExcelLoader

            loader = ExcelLoader()
            workers = loader.load_workers(file_path)
            return [
                {
                    "id": w.id,
                    "name": w.name,
                    "worker_type": w.worker_type or "",
                }
                for w in workers
            ]
    return []


def _import_workers(rows: list[dict[str, Any]]) -> tuple[int, int]:
    """Import worker rows, skipping duplicates. Returns (created, skipped)."""
    created = 0
    skipped = 0
    existing_ids = set(
        Worker.objects.values_list("worker_id", flat=True)
    )

    for row in rows:
        worker_id = row.get("id", "")
        if worker_id in existing_ids:
            skipped += 1
            continue

        Worker.objects.create(
            worker_id=worker_id,
            name=row.get("name", ""),
            worker_type=row.get("worker_type", ""),
        )
        existing_ids.add(worker_id)
        created += 1

    return created, skipped
