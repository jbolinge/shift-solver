---
id: scheduler-125
title: "Import/export from web UI"
type: feature
status: closed
closed: 2026-02-26
priority: 2
created: 2026-02-21
updated: 2026-02-21
parent: scheduler-109
depends-on: scheduler-123
labels: [web, django, io, import, export]
---

# Import/export from web UI

Build web UI for importing worker/shift data from CSV/Excel files and exporting schedules to various formats.

## Description

Create import and export functionality accessible from the web UI. Users can upload CSV or Excel files to bulk-import workers, shift types, and availability data. Users can export solver results to Excel, JSON, or Plotly formats directly from the web interface.

## Files to Create

- `web/core/views/import_views.py` - Data import views
- `web/core/views/export_views.py` - Schedule export views
- `web/templates/io/import_page.html` - Import page with file upload
- `web/templates/io/import_preview.html` - Import preview/confirmation partial
- `web/templates/io/export_page.html` - Export options page
- `tests/test_web/test_import_views.py` - Import view tests
- `tests/test_web/test_export_views.py` - Export view tests

## Files to Modify

- `web/core/urls.py` - Add import/export URL patterns

## Implementation

### URL Patterns

```python
urlpatterns += [
    path("import/", ImportPageView.as_view(), name="import-page"),
    path("import/upload/", ImportUploadView.as_view(), name="import-upload"),
    path("import/preview/", ImportPreviewView.as_view(), name="import-preview"),
    path("import/confirm/", ImportConfirmView.as_view(), name="import-confirm"),
    path("solver-runs/<int:pk>/export/", ExportPageView.as_view(), name="export-page"),
    path("solver-runs/<int:pk>/export/<str:format>/", ExportDownloadView.as_view(), name="export-download"),
]
```

### Import Flow

1. User navigates to import page
2. Selects data type (workers, shift types, availability)
3. Uploads CSV or Excel file
4. System parses file, shows preview with validation
5. User confirms import
6. Data saved to Django ORM models

### Import Preview

Shows a table of parsed records with:
- Row number
- Parsed field values
- Validation status (valid/error with message)
- Checkbox to include/exclude rows

### Export Formats

- **Excel**: Uses existing `ExcelHandler` via conversion layer
- **JSON**: Schedule data as JSON file download
- **Plotly**: Redirects to chart download (scheduler-124)

### Integration with Existing IO

```python
from shift_solver.io import ExcelHandler, CSVHandler
```

Use existing handlers via the conversion layer to translate between Django ORM and domain objects.

## Tests (write first)

```python
class TestImportPage:
    def test_import_page_returns_200(self, client):
        """Import page returns HTTP 200."""

    def test_import_page_has_file_upload(self, client):
        """Import page includes file upload form."""

class TestImportUpload:
    def test_upload_csv_workers(self, client, tmp_path):
        """Uploading a CSV file with worker data parses correctly."""

    def test_upload_invalid_file_type(self, client):
        """Uploading unsupported file type returns error."""

    def test_upload_preview_shows_parsed_rows(self, client, tmp_path):
        """Upload preview displays parsed data for confirmation."""

class TestImportConfirm:
    def test_confirm_import_creates_workers(self, client):
        """Confirming import creates worker records in database."""

    def test_confirm_import_skips_invalid_rows(self, client):
        """Invalid rows are skipped during import."""

class TestExportPage:
    def test_export_page_returns_200(self, client, completed_solver_run):
        """Export page returns HTTP 200."""

class TestExportDownload:
    def test_export_excel_returns_file(self, client, completed_solver_run):
        """Excel export returns downloadable file."""

    def test_export_json_returns_file(self, client, completed_solver_run):
        """JSON export returns downloadable file."""

    def test_export_invalid_format_returns_400(self, client, completed_solver_run):
        """Unknown export format returns HTTP 400."""
```

## Acceptance Criteria

- [ ] Tests written before implementation
- [ ] CSV and Excel file upload for workers, shift types, availability
- [ ] Import preview with validation before committing
- [ ] Invalid rows highlighted with error messages
- [ ] Excel and JSON export download for solver results
- [ ] Reuses existing IO handlers via conversion layer
- [ ] All 11 tests pass
- [ ] ruff and mypy clean
- [ ] Frequent, focused commits
