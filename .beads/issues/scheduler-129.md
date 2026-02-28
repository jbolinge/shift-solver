---
id: scheduler-129
title: "Custom Template Tag Library"
type: task
status: open
priority: 1
created: 2026-02-27
updated: 2026-02-27
parent: scheduler-127
labels: [web, django, templates]
---

# Custom Template Tag Library

Create `{% status_badge %}` and `{% render_field %}` template tags to eliminate copy-pasted badge HTML and enable consistent field rendering with help text.

## Description

Status badge HTML is duplicated across 8+ templates with slight variations. Help text is defined on forms but never rendered in any template. This task creates a reusable template tag library that solves both problems:

- `status_badge` — simple tag that renders a styled colored badge span
- `render_field` — inclusion tag that renders a complete field block (label + widget + help text + errors)

## Files to Create

- `web/core/templatetags/__init__.py` — Package init (empty file)
- `web/core/templatetags/ui_tags.py` — Template tag definitions
- `web/templates/partials/_field.html` — Field rendering partial template

## Files to Modify

None in this task (adoption happens in scheduler-130).

## Implementation

### ui_tags.py

```python
from django import template
from django.utils.html import format_html

register = template.Library()


@register.simple_tag
def status_badge(text, color="gray"):
    """Render a styled status badge.

    Usage: {% status_badge "Active" "green" %}
    """
    color_classes = {
        "green": "bg-green-100 text-green-800",
        "red": "bg-red-100 text-red-800",
        "yellow": "bg-yellow-100 text-yellow-800",
        "blue": "bg-blue-100 text-blue-800",
        "gray": "bg-gray-100 text-gray-800",
        "indigo": "bg-indigo-100 text-indigo-800",
        "purple": "bg-purple-100 text-purple-800",
    }
    classes = color_classes.get(color, color_classes["gray"])
    return format_html(
        '<span class="inline-flex items-center rounded-full px-2.5 py-0.5 '
        'text-xs font-medium {}">{}</span>',
        classes, text,
    )


@register.inclusion_tag("partials/_field.html")
def render_field(field):
    """Render a complete form field with label, widget, help text, and errors.

    Usage: {% render_field form.name %}
    """
    return {"field": field}
```

### _field.html

```html
<div class="mb-4">
    <label for="{{ field.id_for_label }}" class="block text-sm font-medium text-gray-700 mb-1">
        {{ field.label }}
    </label>
    {{ field }}
    {% if field.help_text %}
        <p class="mt-1 text-sm text-gray-500">{{ field.help_text }}</p>
    {% endif %}
    {% if field.errors %}
        {% for error in field.errors %}
            <p class="mt-1 text-sm text-red-600">{{ error }}</p>
        {% endfor %}
    {% endif %}
</div>
```

## Tests (write first)

File: `tests/test_web/test_template_tags.py`

```python
import pytest
from django.template import Template, Context


@pytest.mark.django_db
class TestStatusBadge:
    def test_renders_green_badge(self):
        """Green badge has correct CSS classes."""
        tpl = Template('{% load ui_tags %}{% status_badge "Active" "green" %}')
        html = tpl.render(Context())
        assert "bg-green-100" in html
        assert "text-green-800" in html
        assert "Active" in html

    def test_renders_red_badge(self):
        """Red badge has correct CSS classes."""
        tpl = Template('{% load ui_tags %}{% status_badge "Inactive" "red" %}')
        html = tpl.render(Context())
        assert "bg-red-100" in html
        assert "Inactive" in html

    def test_default_color_is_gray(self):
        """Badge without color argument defaults to gray."""
        tpl = Template('{% load ui_tags %}{% status_badge "Unknown" %}')
        html = tpl.render(Context())
        assert "bg-gray-100" in html

    def test_unknown_color_falls_back_to_gray(self):
        """Unknown color name falls back to gray."""
        tpl = Template('{% load ui_tags %}{% status_badge "Test" "magenta" %}')
        html = tpl.render(Context())
        assert "bg-gray-100" in html


@pytest.mark.django_db
class TestRenderField:
    def test_renders_label(self):
        """render_field includes the field label."""
        from web.core.forms import WorkerForm
        form = WorkerForm()
        tpl = Template('{% load ui_tags %}{% render_field form.name %}')
        html = tpl.render(Context({"form": form}))
        assert "<label" in html

    def test_renders_help_text(self):
        """render_field shows help_text when defined on the field."""
        from web.core.forms import WorkerForm
        form = WorkerForm()
        # Find a field with help_text
        for name, field in form.fields.items():
            if field.help_text:
                tpl = Template(f'{{% load ui_tags %}}{{% render_field form.{name} %}}')
                html = tpl.render(Context({"form": form}))
                assert "text-gray-500" in html
                assert str(field.help_text) in html
                break

    def test_renders_errors(self):
        """render_field shows validation errors."""
        from web.core.forms import WorkerForm
        form = WorkerForm(data={})  # Empty data triggers required errors
        if not form.is_valid():
            for name, field in form.fields.items():
                if form[name].errors:
                    tpl = Template(f'{{% load ui_tags %}}{{% render_field form.{name} %}}')
                    html = tpl.render(Context({"form": form}))
                    assert "text-red-600" in html
                    break
```

## Acceptance Criteria

- [ ] `{% load ui_tags %}` works in templates
- [ ] `{% status_badge "Active" "green" %}` renders a colored badge span with correct classes
- [ ] `{% render_field form.field_name %}` renders label, widget, help text, and error messages
- [ ] Default and fallback colors work correctly
- [ ] Help text that was previously defined but never shown will now appear when tags are adopted
- [ ] Tests pass: `uv run pytest tests/test_web/test_template_tags.py`
- [ ] Lint clean: `uv run ruff check web/`
- [ ] Commit: `feat: add custom template tag library for badges and field rendering`
