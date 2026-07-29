"""Data import views for CSV/Excel file upload."""

import datetime
import tempfile
from pathlib import Path
from typing import Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from core.models import Availability, ScheduleRequest, ShiftType, Worker, WorkerRequest


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

    max_bytes = settings.MAX_IMPORT_FILE_SIZE
    if uploaded_file.size and uploaded_file.size > max_bytes:
        return render(
            request,
            "io/import_page.html",
            {
                "errors": [
                    f"File too large ({uploaded_file.size:,} bytes). "
                    f"Maximum allowed size is {max_bytes // (1024 * 1024)} MB."
                ]
            },
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

    context: dict[str, Any] = {
        "rows": parsed_rows,
        "data_type": data_type,
        "count": len(parsed_rows),
    }
    # Worker requests must attach to a specific ScheduleRequest; offer a target
    # selector instead of silently importing into the most recent one.
    if data_type == "requests":
        context["schedule_requests"] = ScheduleRequest.objects.order_by(
            "-created_at"
        )
    return render(request, "io/import_preview.html", context)


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
    target_name = None

    if data_type == "workers":
        created_count, skipped_count = _import_workers(parsed_rows)
    elif data_type == "availability":
        created_count, skipped_count = _import_availability(parsed_rows)
    elif data_type == "requests":
        target_id = request.POST.get("target_request_id") or None
        target = _resolve_target_request(target_id)
        if target is None:
            return render(
                request,
                "io/import_page.html",
                {"errors": ["No schedule request available to import into."]},
            )
        created_count, skipped_count = _import_requests(parsed_rows, target)
        target_name = target.name

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
            "target_name": target_name,
        },
    )


def _parse_file(
    file_path: Path, ext: str, data_type: str
) -> list[dict[str, Any]]:
    """Parse uploaded file into list of row dicts."""
    if data_type == "workers":
        if ext == ".csv":
            from shift_solver.io import CSVLoader

            workers = CSVLoader().load_workers(file_path)
        elif ext == ".xlsx":
            from shift_solver.io import ExcelLoader

            workers = ExcelLoader().load_workers(file_path)
        else:
            return []
        return [
            {
                "id": w.id,
                "name": w.name,
                "worker_type": w.worker_type or "",
                "restricted_shifts": sorted(w.restricted_shifts) if w.restricted_shifts else [],
            }
            for w in workers
        ]

    if data_type == "availability":
        if ext == ".csv":
            from shift_solver.io import CSVLoader

            avails = CSVLoader().load_availability(file_path)
        elif ext == ".xlsx":
            from shift_solver.io import ExcelLoader

            avails = ExcelLoader().load_availability(file_path)
        else:
            return []
        return [
            {
                "worker_id": a.worker_id,
                "start_date": a.start_date.isoformat(),
                "end_date": a.end_date.isoformat(),
                "availability_type": a.availability_type,
                "shift_type_id": a.shift_type_id or "",
            }
            for a in avails
        ]

    if data_type == "requests":
        if ext == ".csv":
            from shift_solver.io import CSVLoader

            reqs = CSVLoader().load_requests(file_path)
        elif ext == ".xlsx":
            from shift_solver.io import ExcelLoader

            reqs = ExcelLoader().load_requests(file_path)
        else:
            return []
        return [
            {
                "worker_id": r.worker_id,
                "start_date": r.start_date.isoformat(),
                "end_date": r.end_date.isoformat(),
                "request_type": r.request_type,
                "shift_type_id": r.shift_type_id,
                "priority": r.priority,
            }
            for r in reqs
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
            restricted_shifts=row.get("restricted_shifts", []),
        )
        existing_ids.add(worker_id)
        created += 1

    return created, skipped


def _import_availability(rows: list[dict[str, Any]]) -> tuple[int, int]:
    """Import availability rows. Returns (created, skipped).

    Only "unavailable" entries are imported; the solver does not honor any other
    availability type, so other rows are skipped.
    """
    created = 0
    skipped = 0

    worker_map = {str(w.worker_id): w for w in Worker.objects.all()}
    shift_type_map = {str(s.shift_type_id): s for s in ShiftType.objects.all()}

    for row in rows:
        worker = worker_map.get(row.get("worker_id", ""))
        if not worker:
            skipped += 1
            continue

        # Only "unavailable" affects the solver; skip preferred/required/etc.
        if row.get("availability_type", "unavailable") != "unavailable":
            skipped += 1
            continue

        start_date = datetime.date.fromisoformat(row["start_date"])
        end_date = datetime.date.fromisoformat(row["end_date"])
        status_fields = {"is_available": False}

        shift_type_id_str = row.get("shift_type_id", "")
        shift_type = shift_type_map.get(shift_type_id_str) if shift_type_id_str else None

        current = start_date
        while current <= end_date:
            _, was_created = Availability.objects.update_or_create(
                worker=worker,
                date=current,
                shift_type=shift_type,
                defaults=status_fields,
            )
            if was_created:
                created += 1
            else:
                skipped += 1
            current += datetime.timedelta(days=1)

    return created, skipped


def _resolve_target_request(
    target_id: str | None,
) -> ScheduleRequest | None:
    """Resolve the ScheduleRequest to import worker requests into.

    Uses the explicitly selected request when valid, otherwise falls back to
    the most recent one. Returns None when no schedule request exists.
    """
    if target_id:
        target = ScheduleRequest.objects.filter(pk=target_id).first()
        if target is not None:
            return target
    return ScheduleRequest.objects.order_by("-created_at").first()


def _import_requests(
    rows: list[dict[str, Any]],
    schedule_request: ScheduleRequest,
) -> tuple[int, int]:
    """Import scheduling request rows into ``schedule_request``.

    Returns (created, skipped).
    """
    created = 0
    skipped = 0

    worker_map = {str(w.worker_id): w for w in Worker.objects.all()}
    shift_type_map = {str(s.shift_type_id): s for s in ShiftType.objects.all()}

    for row in rows:
        worker = worker_map.get(row.get("worker_id", ""))
        shift_type = shift_type_map.get(row.get("shift_type_id", ""))
        if not worker or not shift_type:
            skipped += 1
            continue

        start_date = datetime.date.fromisoformat(row["start_date"])
        end_date = datetime.date.fromisoformat(row["end_date"])
        request_type = row.get("request_type", "negative")
        priority = int(row.get("priority", 1))

        WorkerRequest.objects.create(
            schedule_request=schedule_request,
            worker=worker,
            shift_type=shift_type,
            start_date=start_date,
            end_date=end_date,
            request_type=request_type,
            priority=priority,
        )
        created += 1

    return created, skipped
