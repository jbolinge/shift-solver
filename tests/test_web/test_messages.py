"""Tests for messages auto-dismiss and global toast system (scheduler-132)."""

from pathlib import Path

import pytest


class TestToastCSS:
    def test_custom_css_contains_toast_keyframes(self):
        """custom.css defines toast-in and toast-out animations."""
        css_path = Path("web/static/css/custom.css")
        css = css_path.read_text()
        assert "toast-in" in css
        assert "toast-out" in css
        assert "@keyframes" in css

    def test_custom_css_contains_toast_classes(self):
        """custom.css defines .toast-enter and .toast-exit classes."""
        css_path = Path("web/static/css/custom.css")
        css = css_path.read_text()
        assert ".toast-enter" in css
        assert ".toast-exit" in css


class TestMessagesDismissTemplate:
    def test_messages_have_dismiss_button(self):
        """Messages template includes a dismiss button."""
        template = Path("web/templates/partials/_messages.html").read_text()
        assert "Dismiss" in template or "&times;" in template or "×" in template

    def test_messages_have_auto_dismiss_attribute(self):
        """Messages template includes data-auto-dismiss attribute."""
        template = Path("web/templates/partials/_messages.html").read_text()
        assert "data-auto-dismiss" in template


@pytest.mark.django_db
class TestGlobalToastContainer:
    def test_base_has_toast_container(self, client):
        """base.html includes a global #toast-container."""
        response = client.get("/")
        html = response.content.decode()
        assert 'id="toast-container"' in html

    def test_toast_container_has_aria_live(self, client):
        """Global toast container has aria-live='polite'."""
        response = client.get("/")
        html = response.content.decode()
        assert 'aria-live="polite"' in html

    def test_availability_page_no_inline_toast_styles(self):
        """Availability page no longer has inline toast style block."""
        template_path = Path("web/templates/availability/availability_page.html")
        if template_path.exists():
            content = template_path.read_text()
            assert "@keyframes toast-in" not in content

    def test_custom_css_loaded_in_base(self):
        """base.html loads custom.css via {% static %} tag."""
        template = Path("web/templates/base.html").read_text()
        assert "custom.css" in template
