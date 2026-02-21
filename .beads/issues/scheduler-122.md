---
id: scheduler-122
title: "Solver execution UI: launch, progress, results"
type: feature
status: open
priority: 1
created: 2026-02-21
updated: 2026-02-21
parent: scheduler-109
depends-on: scheduler-121
labels: [web, django, htmx, solver, ui]
---

# Solver execution UI: launch, progress, results

Build the web UI for launching solver runs, monitoring progress with live updates, and viewing results.

## Description

Create views for the solver execution workflow: a "Solve" button on the schedule request detail page, a progress tracking page with HTMX polling for live updates, and a results summary page showing solve statistics.

## Files to Create

- `web/core/views/solver_views.py` - Solver execution views
- `web/templates/solver/solve_launch.html` - Launch confirmation page
- `web/templates/solver/solve_progress.html` - Progress tracking page
- `web/templates/solver/solve_progress_bar.html` - Progress bar partial (for HTMX polling)
- `web/templates/solver/solve_results.html` - Results summary page
- `tests/test_web/test_solver_views.py` - Solver view tests

## Files to Modify

- `web/core/urls.py` - Add solver URL patterns

## Implementation

### URL Patterns

```python
urlpatterns += [
    path("requests/<int:pk>/solve/", SolveLaunchView.as_view(), name="solve-launch"),
    path("solver-runs/<int:pk>/progress/", SolveProgressView.as_view(), name="solve-progress"),
    path("solver-runs/<int:pk>/progress-bar/", SolveProgressBarView.as_view(), name="solve-progress-bar"),
    path("solver-runs/<int:pk>/results/", SolveResultsView.as_view(), name="solve-results"),
]
```

### Launch Flow

1. User clicks "Solve" on request detail page
2. Launch view validates request is ready (has workers, shift types, constraints)
3. Creates a `SolverRun` record, starts `SolverRunner`
4. Redirects to progress page

### Progress Page

```html
<!-- Progress bar with HTMX polling every 2 seconds -->
<div hx-get="{% url 'solve-progress-bar' run.pk %}"
     hx-trigger="every 2s"
     hx-swap="innerHTML">
    {% include "solver/solve_progress_bar.html" %}
</div>
```

Progress bar partial shows:
- Percentage bar with animation
- Status text (Running..., Completed, Failed)
- Elapsed time
- Auto-redirects to results page on completion (via HX-Redirect header)

### Results Summary

Displays:
- Solve status and duration
- Number of assignments generated
- Objective value (if applicable)
- Assignment counts by shift type
- Links to schedule visualization and export

## Tests (write first)

```python
class TestSolveLaunchView:
    def test_launch_creates_solver_run(self, client, schedule_request):
        """Launching a solve creates a SolverRun record."""

    def test_launch_redirects_to_progress(self, client, schedule_request):
        """Launch redirects to the progress tracking page."""

    def test_launch_validates_request_has_workers(self, client, empty_request):
        """Launch rejects request with no workers available."""

class TestSolveProgressView:
    def test_progress_page_returns_200(self, client, solver_run):
        """Progress page returns HTTP 200."""

    def test_progress_bar_returns_partial(self, client, solver_run):
        """Progress bar endpoint returns HTML partial with percentage."""

    def test_completed_run_redirects_to_results(self, client, completed_solver_run):
        """Progress bar for completed run includes HX-Redirect to results."""

class TestSolveResultsView:
    def test_results_page_returns_200(self, client, completed_solver_run):
        """Results page returns HTTP 200 for completed run."""

    def test_results_shows_assignment_count(self, client, completed_solver_run):
        """Results page shows the number of assignments generated."""

    def test_results_shows_duration(self, client, completed_solver_run):
        """Results page shows solve duration."""

    def test_failed_run_shows_error(self, client, failed_solver_run):
        """Results page for failed run shows error message."""
```

## Acceptance Criteria

- [ ] Tests written before implementation
- [ ] "Solve" button launches background solver run
- [ ] Progress page shows live progress bar with HTMX polling
- [ ] Auto-redirect to results when solve completes
- [ ] Results page shows solve statistics and assignment counts
- [ ] Failed runs display error message
- [ ] Validation prevents launching with incomplete configuration
- [ ] All 10 tests pass
- [ ] ruff and mypy clean
- [ ] Frequent, focused commits
