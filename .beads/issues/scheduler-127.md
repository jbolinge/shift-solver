---
id: scheduler-127
title: "UI/UX Modernization"
type: epic
status: open
priority: 1
created: 2026-02-27
updated: 2026-02-27
labels: [web, templates, tailwind, quality]
---

# UI/UX Modernization

Bring the shift-solver web UI up to modern standards across 8 independently-committable TDD phases covering code quality (DRY), accessibility, responsiveness, and user experience.

## Summary

The web UI is functional but has significant code quality and UX gaps:
- ~30 repeated Tailwind class strings in form widgets (DRY violation)
- Copy-pasted status badge HTML across 8+ templates
- Missing accessibility attributes (no ARIA roles on modals/messages, no skip-to-content, no active sidebar state)
- Help text defined on forms but never rendered
- Non-dismissible flash messages
- `alert()` used for event details in calendar views
- Sparse dashboard with no quick actions or recent activity
- No mobile responsiveness for sidebar navigation

This epic addresses all of these through 8 focused tasks.

## Child Issues

### Phase 1: Code Quality
- **scheduler-128** — Form Widget CSS Constants (DRY)

### Phase 2: Template Infrastructure
- **scheduler-129** — Custom Template Tag Library

### Phase 3: Template Adoption
- **scheduler-130** — Adopt Template Tags Across Templates (depends on scheduler-129)

### Phase 4: Accessibility
- **scheduler-131** — Accessibility Improvements (depends on scheduler-129)

### Phase 5: Messages
- **scheduler-132** — Messages Auto-Dismiss & Global Toast System (depends on scheduler-131)

### Phase 6: Responsive Layout
- **scheduler-133** — Responsive Sidebar with Mobile Hamburger (depends on scheduler-131)

### Phase 7: Calendar UX
- **scheduler-134** — Replace alert() with Event Popover

### Phase 8: Dashboard
- **scheduler-135** — Dashboard Enhancement & HTMX Loading Indicator

## Dependency Chain

```
scheduler-128 (forms DRY)              — independent
scheduler-129 (template tags)          — independent
scheduler-130 (adopt tags)             — depends on scheduler-129
scheduler-131 (accessibility)          — depends on scheduler-129
scheduler-132 (messages/toast)         — depends on scheduler-131
scheduler-133 (responsive sidebar)     — depends on scheduler-131
scheduler-134 (event popover)          — independent
scheduler-135 (dashboard/loading)      — independent
```

## Branch

`feature/ui-ux-improvements` off `main`

## Verification Checklist

**Per-task**:
1. `uv run pytest tests/test_web/` — All existing + new tests pass
2. `uv run python web/manage.py runserver` — Visual spot-check of affected pages
3. `uv run ruff check web/` — No lint errors introduced

**Full end-to-end after all 8 tasks**:
1. `uv run pytest` — Full test suite green
2. Navigate: Dashboard → Workers → Shifts → Availability → Constraints → Requests → Solve → Results → Charts → Export
3. Test mobile viewport: sidebar collapses, hamburger toggles it
4. Test keyboard navigation: Tab through sidebar, Escape closes modal, skip-to-content link works
5. Screen reader check: messages announced, modal labeled, badges have text content

## Acceptance Criteria

- [ ] All 8 child tasks completed with TDD workflow
- [ ] Zero DRY violations in form widget classes
- [ ] Template tags used consistently across all templates
- [ ] Full ARIA accessibility on modals, messages, sidebar, and navigation
- [ ] Messages auto-dismiss and have manual close buttons
- [ ] Responsive sidebar with mobile hamburger toggle
- [ ] No `alert()` calls in JavaScript files
- [ ] Enhanced dashboard with quick actions and recent activity
- [ ] Global HTMX loading indicator
- [ ] All tests pass, ruff clean
