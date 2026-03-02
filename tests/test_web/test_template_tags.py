"""Tests for custom template tag library (scheduler-129)."""

import pytest
from django.template import Context, Template


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

    def test_renders_span_element(self):
        """Badge renders as a span element."""
        tpl = Template('{% load ui_tags %}{% status_badge "OK" "blue" %}')
        html = tpl.render(Context())
        assert "<span" in html
        assert "rounded-full" in html

    def test_all_supported_colors(self):
        """All documented colors render their specific classes."""
        colors = ["green", "red", "yellow", "blue", "gray", "indigo", "purple"]
        for color in colors:
            tpl = Template(f'{{% load ui_tags %}}{{% status_badge "X" "{color}" %}}')
            html = tpl.render(Context())
            assert f"bg-{color}-100" in html
            assert f"text-{color}-800" in html


@pytest.mark.django_db
class TestRenderField:
    def test_renders_label(self):
        """render_field includes the field label."""
        from core.forms import WorkerForm

        form = WorkerForm()
        tpl = Template("{% load ui_tags %}{% render_field form.name %}")
        html = tpl.render(Context({"form": form}))
        assert "<label" in html

    def test_renders_widget(self):
        """render_field includes the form widget."""
        from core.forms import WorkerForm

        form = WorkerForm()
        tpl = Template("{% load ui_tags %}{% render_field form.name %}")
        html = tpl.render(Context({"form": form}))
        assert "<input" in html

    def test_renders_help_text(self):
        """render_field shows help_text when defined on the field."""
        from core.forms import WorkerForm

        form = WorkerForm()
        for name, field in form.fields.items():
            if field.help_text:
                tpl = Template(
                    f"{{% load ui_tags %}}{{% render_field form.{name} %}}"
                )
                html = tpl.render(Context({"form": form}))
                assert "text-gray-500" in html
                assert str(field.help_text) in html
                break

    def test_renders_errors(self):
        """render_field shows validation errors."""
        from core.forms import WorkerForm

        form = WorkerForm(data={})
        form.is_valid()
        for name in form.fields:
            if form[name].errors:
                tpl = Template(
                    f"{{% load ui_tags %}}{{% render_field form.{name} %}}"
                )
                html = tpl.render(Context({"form": form}))
                assert "text-red-600" in html
                break
