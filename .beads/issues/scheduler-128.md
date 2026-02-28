---
id: scheduler-128
title: "Form Widget CSS Constants (DRY)"
type: task
status: open
priority: 1
created: 2026-02-27
updated: 2026-02-27
parent: scheduler-127
labels: [web, templates, tailwind]
---

# Form Widget CSS Constants (DRY)

Extract the repeated Tailwind class strings from ~30 widget `attrs` into 3 module-level constants, eliminating DRY violations in form definitions.

## Description

Currently, every form widget in `web/core/forms.py` has inline Tailwind class strings like `"w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"` copied verbatim ~30 times. Extract these into named constants for maintainability.

## Files to Modify

- `web/core/forms.py` — Add 3 module-level constants; replace all inline class strings

## Implementation

### Constants to Define

```python
# Module-level CSS constants (top of forms.py)
CSS_INPUT = (
    "w-full rounded-md border-gray-300 shadow-sm "
    "focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
)

CSS_CHECKBOX = (
    "rounded border-gray-300 text-indigo-600 shadow-sm "
    "focus:border-indigo-500 focus:ring-indigo-500"
)

CSS_TEXTAREA_MONO = (
    "w-full rounded-md border-gray-300 shadow-sm "
    "focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm font-mono"
)
```

### Refactoring

Replace every occurrence of inline class strings in widget `attrs={'class': ...}` with the appropriate constant. All 6 form classes should be updated.

## Tests (write first)

File: `tests/test_web/test_form_widget_classes.py`

```python
import pytest
from web.core.forms import (
    CSS_INPUT, CSS_CHECKBOX, CSS_TEXTAREA_MONO,
    WorkerForm, ShiftTypeForm, ConstraintForm,
    ScheduleRequestForm, WorkerRequestForm, SettingsForm,
)


class TestCSSConstants:
    def test_css_input_constant_exported(self):
        """CSS_INPUT constant is a non-empty string."""
        assert isinstance(CSS_INPUT, str) and len(CSS_INPUT) > 0

    def test_css_checkbox_constant_exported(self):
        """CSS_CHECKBOX constant is a non-empty string."""
        assert isinstance(CSS_CHECKBOX, str) and len(CSS_CHECKBOX) > 0

    def test_css_textarea_mono_constant_exported(self):
        """CSS_TEXTAREA_MONO constant contains font-mono."""
        assert "font-mono" in CSS_TEXTAREA_MONO


class TestFormWidgetsUseConstants:
    @pytest.mark.parametrize("form_class", [
        WorkerForm, ShiftTypeForm, ConstraintForm,
        ScheduleRequestForm, WorkerRequestForm, SettingsForm,
    ])
    def test_all_text_inputs_use_css_input(self, form_class):
        """Every TextInput/Select/NumberInput widget uses CSS_INPUT constant."""
        form = form_class()
        for field in form.fields.values():
            widget = field.widget
            css = widget.attrs.get("class", "")
            if css and "font-mono" not in css and "rounded" in css:
                assert css == CSS_INPUT or css == CSS_CHECKBOX

    @pytest.mark.parametrize("form_class", [
        WorkerForm, ShiftTypeForm, ConstraintForm,
        ScheduleRequestForm, WorkerRequestForm, SettingsForm,
    ])
    def test_no_inline_duplicate_classes(self, form_class):
        """No two fields in the same form have identical long class strings defined inline."""
        form = form_class()
        classes = [
            field.widget.attrs.get("class", "")
            for field in form.fields.values()
            if field.widget.attrs.get("class")
        ]
        # All class strings should be one of the 3 constants
        valid = {CSS_INPUT, CSS_CHECKBOX, CSS_TEXTAREA_MONO}
        for css in classes:
            if len(css) > 20:  # Skip short/custom classes
                assert css in valid, f"Found non-constant class string: {css[:50]}..."
```

## Acceptance Criteria

- [ ] Three CSS constants (`CSS_INPUT`, `CSS_CHECKBOX`, `CSS_TEXTAREA_MONO`) defined as module-level constants
- [ ] All ~30 widget `attrs` reference constants instead of inline strings
- [ ] All 6 form classes updated
- [ ] Tests pass: `uv run pytest tests/test_web/test_form_widget_classes.py`
- [ ] Lint clean: `uv run ruff check web/`
- [ ] Commit: `refactor: extract shared CSS class constants in forms.py`
