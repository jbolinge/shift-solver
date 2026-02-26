---
id: scheduler-109
title: "Django + HTMX + FullCalendar Web UI"
type: epic
status: closed
closed: 2026-02-26
priority: 1
created: 2026-02-21
updated: 2026-02-21
labels: [web, django, htmx, fullcalendar]
---

# Django + HTMX + FullCalendar Web UI

Build a web-based UI for the shift-solver using Django, HTMX for dynamic interactions, FullCalendar.io for calendar views, Tailwind CSS for styling, and django-unfold for admin customization.

## Summary

Add a `web/` Django project alongside the existing `src/shift_solver/` package. The CLI continues working unchanged. A conversion layer bridges Django ORM models to the existing domain dataclasses, allowing the solver engine to remain untouched while the web UI provides a rich interactive experience for managing workers, shift types, availability, constraints, solver runs, and schedule visualization.

## Architecture

- **Django project**: `web/` directory at repository root alongside `src/`
- **CLI unchanged**: Existing `src/shift_solver/cli/` continues to work as-is
- **Conversion layer**: `web/core/converters.py` bridges Django ORM models to domain dataclasses
- **Background solver**: `threading.Thread` + `SolverRun` DB model for status tracking
- **FullCalendar**: JSON endpoints serve calendar data, user actions via HTMX partial updates
- **Plotly embedding**: Existing Plotly charts served via iframe or inline HTML

### Stack

| Component | Technology |
|-----------|------------|
| Backend | Django 5.x |
| Interactivity | HTMX 2.x |
| Calendar | FullCalendar 6.x |
| Styling | Tailwind CSS 3.x |
| Admin | django-unfold |
| Database | SQLite (Django ORM) |
| Solver | Existing OR-Tools CP-SAT (via conversion layer) |

## Child Issues

### Phase 1: Foundation
- **scheduler-110** - Django project skeleton and settings
- **scheduler-111** - Django ORM models (migrate from SQLAlchemy) (depends on scheduler-110)
- **scheduler-112** - Domain dataclass conversion layer (depends on scheduler-111)
- **scheduler-113** - Base templates, Tailwind CSS, HTMX setup (depends on scheduler-110)
- **scheduler-114** - Django admin with django-unfold (depends on scheduler-111)

### Phase 2: Core Data Entry
- **scheduler-115** - Worker CRUD views with HTMX (depends on scheduler-113, scheduler-112)
- **scheduler-116** - Shift type CRUD views with HTMX (depends on scheduler-113, scheduler-112)
- **scheduler-117** - Availability calendar with FullCalendar (depends on scheduler-115, scheduler-116)
- **scheduler-118** - Scheduling request management (depends on scheduler-117)

### Phase 3: Configuration
- **scheduler-119** - Constraint configuration UI (depends on scheduler-116)
- **scheduler-120** - Schedule parameters and solver settings UI (depends on scheduler-119)

### Phase 4: Solver Integration
- **scheduler-121** - Background solver runner with progress tracking (depends on scheduler-112, scheduler-120)
- **scheduler-122** - Solver execution UI: launch, progress, results (depends on scheduler-121)

### Phase 5: Results & Output
- **scheduler-123** - Schedule visualization with FullCalendar (depends on scheduler-122)
- **scheduler-124** - Plotly chart embedding and export (depends on scheduler-123)
- **scheduler-125** - Import/export from web UI (depends on scheduler-123)

### Phase 6: Quality
- **scheduler-126** - E2E tests for web UI workflows (depends on scheduler-125)

## Dependency Chain

```
scheduler-110  (Django skeleton)
    ├── scheduler-111  (ORM models)
    │       ├── scheduler-112  (conversion layer)
    │       │       ├── scheduler-115  (worker CRUD)  ←─┐
    │       │       ├── scheduler-116  (shift type CRUD) ←── scheduler-113 (templates)
    │       │       │       ├── scheduler-117  (availability calendar)
    │       │       │       │       └── scheduler-118  (requests)
    │       │       │       └── scheduler-119  (constraint config)
    │       │       │               └── scheduler-120  (solver settings)
    │       │       │                       └── scheduler-121  (solver runner)
    │       │       │                               └── scheduler-122  (solver UI)
    │       │       │                                       └── scheduler-123  (schedule viz)
    │       │       │                                               ├── scheduler-124  (plotly)
    │       │       │                                               └── scheduler-125  (import/export)
    │       │       │                                                       └── scheduler-126  (E2E)
    │       └── scheduler-114  (admin)
    └── scheduler-113  (base templates)
```

## Branch

`feature/web-ui` off `main`

## Acceptance Criteria

- [ ] Django web UI serves at localhost with worker/shift/schedule management
- [ ] FullCalendar calendar views for availability and schedule visualization
- [ ] HTMX-powered CRUD without full page reloads
- [ ] Background solver execution with progress tracking
- [ ] Existing CLI and solver engine unchanged
- [ ] Conversion layer correctly bridges Django ORM to domain dataclasses
- [ ] TDD: tests written before implementation for every component
- [ ] All tests pass (existing + new)
- [ ] ruff and mypy clean
