---
id: scheduler-110
title: "Django project skeleton and settings"
type: task
status: closed
priority: 1
created: 2026-02-21
updated: 2026-02-21
parent: scheduler-109
labels: [web, django, foundation]
---

# Django project skeleton and settings

Create the Django project structure under `web/`, configure settings for development, and verify the dev server starts cleanly.

## Description

Set up the Django project at `web/` alongside the existing `src/shift_solver/` package. Configure SQLite database, installed apps, middleware, static files, and template directories. Add Django and its dependencies to pyproject.toml. The project should start with `uv run python web/manage.py runserver` and show the default Django welcome page.

## Files to Create

- `web/manage.py` - Django management entry point
- `web/config/__init__.py` - Project config package
- `web/config/settings.py` - Django settings (dev defaults)
- `web/config/urls.py` - Root URL configuration
- `web/config/wsgi.py` - WSGI entry point
- `web/config/asgi.py` - ASGI entry point
- `web/core/__init__.py` - Core app package
- `web/core/apps.py` - Core app config
- `web/templates/base.html` - Minimal base template placeholder

## Files to Modify

- `pyproject.toml` - Add django, django-unfold, whitenoise to dependencies

## Implementation

### Project Layout

```
web/
├── manage.py
├── config/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── core/
│   ├── __init__.py
│   └── apps.py
└── templates/
    └── base.html
```

### Settings Key Decisions

- `BASE_DIR` = `web/` directory
- `DATABASES`: SQLite at `web/db.sqlite3`
- `INSTALLED_APPS`: include `core`, `django.contrib.admin`, `django.contrib.auth`, standard Django apps
- `TEMPLATES.DIRS`: `web/templates/`
- `STATIC_URL`: `/static/`
- `STATICFILES_DIRS`: `web/static/`
- `DEFAULT_AUTO_FIELD`: `django.db.models.BigAutoField`
- `SECRET_KEY`: load from environment with dev fallback
- `DEBUG`: True by default (dev)
- `ALLOWED_HOSTS`: `["*"]` for dev

### sys.path Configuration

`manage.py` adds both `web/` and the repo root to `sys.path` so Django can import the existing `src/shift_solver` package.

## Tests (write first)

```python
class TestDjangoSkeleton:
    def test_django_settings_importable(self):
        """Django settings module can be imported without error."""

    def test_django_check_passes(self):
        """'python manage.py check' passes with no issues."""

    def test_django_urls_importable(self):
        """Root URL configuration can be imported."""

    def test_core_app_config_exists(self):
        """Core app has a valid AppConfig."""

    def test_static_files_configured(self):
        """STATIC_URL and STATICFILES_DIRS are configured."""
```

## Acceptance Criteria

- [ ] Tests written before implementation
- [ ] `uv run python web/manage.py check` passes with no errors
- [ ] `uv run python web/manage.py runserver` starts without error
- [ ] Django, django-unfold, whitenoise added to pyproject.toml
- [ ] Existing CLI (`uv run shift-solver --help`) still works
- [ ] ruff and mypy clean
- [ ] Frequent, focused commits
