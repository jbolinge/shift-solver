"""Tests for CSS constant extraction in form widgets (scheduler-128)."""

import pytest

from core.forms import (
    CSS_CHECKBOX,
    CSS_INPUT,
    CSS_TEXTAREA_MONO,
    ConstraintConfigForm,
    ScheduleRequestForm,
    ShiftTypeForm,
    SolverSettingsForm,
    WorkerForm,
    WorkerRequestForm,
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
    @pytest.mark.parametrize(
        "form_class",
        [
            ConstraintConfigForm,
            WorkerForm,
            ShiftTypeForm,
            ScheduleRequestForm,
            SolverSettingsForm,
            WorkerRequestForm,
        ],
    )
    def test_all_text_inputs_use_css_input(self, form_class):
        """Every TextInput/Select/NumberInput widget uses CSS_INPUT constant."""
        form = form_class()
        for field in form.fields.values():
            widget = field.widget
            css = widget.attrs.get("class", "")
            if css and "font-mono" not in css and "rounded-md" in css:
                assert css == CSS_INPUT, f"Found non-constant class string: {css[:60]}..."

    @pytest.mark.parametrize(
        "form_class",
        [
            ConstraintConfigForm,
            WorkerForm,
            ShiftTypeForm,
            ScheduleRequestForm,
            SolverSettingsForm,
            WorkerRequestForm,
        ],
    )
    def test_no_inline_duplicate_classes(self, form_class):
        """No two fields have identical long class strings defined inline."""
        form = form_class()
        classes = [
            field.widget.attrs.get("class", "")
            for field in form.fields.values()
            if field.widget.attrs.get("class")
        ]
        valid = {CSS_INPUT, CSS_CHECKBOX, CSS_TEXTAREA_MONO}
        for css in classes:
            if len(css) > 20:
                assert css in valid, f"Found non-constant class string: {css[:50]}..."
