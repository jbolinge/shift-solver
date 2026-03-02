"""Tests for accessibility improvements (scheduler-131)."""

import pytest
from django.test import Client


@pytest.mark.django_db
class TestSkipLink:
    def test_skip_to_content_link_present(self, client: Client):
        """Base template contains a skip-to-content link."""
        response = client.get("/")
        html = response.content.decode()
        assert 'href="#main-content"' in html
        assert "Skip to main content" in html

    def test_main_content_id_present(self, client: Client):
        """Main element has id='main-content' target."""
        response = client.get("/")
        html = response.content.decode()
        assert 'id="main-content"' in html


class TestMessagesARIA:
    def test_messages_template_has_role_alert(self):
        """Messages template includes role='alert' on message divs."""
        from pathlib import Path

        template = Path("web/templates/partials/_messages.html").read_text()
        assert 'role="alert"' in template


@pytest.mark.django_db
class TestSidebarAccessibility:
    def test_nav_has_aria_label(self, client: Client):
        """Sidebar nav has aria-label='Main navigation'."""
        response = client.get("/")
        html = response.content.decode()
        assert 'aria-label="Main navigation"' in html

    def test_active_link_has_aria_current(self, client: Client):
        """Active sidebar link has aria-current='page'."""
        response = client.get("/workers/")
        html = response.content.decode()
        assert 'aria-current="page"' in html

    def test_sidebar_uses_url_tags(self):
        """Sidebar template uses {% url %} tags instead of hardcoded paths."""
        from pathlib import Path

        template = Path("web/templates/partials/_sidebar.html").read_text()
        assert "{% url " in template or "{% sidebar_link " in template


@pytest.mark.django_db
class TestModalAccessibility:
    def test_modal_has_dialog_role(self):
        """Solve modal template has role='dialog' and aria-modal='true'."""
        from pathlib import Path

        template = Path("web/templates/solver/solve_modal.html").read_text()
        assert 'role="dialog"' in template
        assert 'aria-modal="true"' in template

    def test_modal_has_aria_labelledby(self):
        """Solve modal has aria-labelledby pointing to heading."""
        from pathlib import Path

        template = Path("web/templates/solver/solve_modal.html").read_text()
        assert "aria-labelledby" in template

    def test_modal_escape_key_handler(self):
        """Solve modal has Escape key handler."""
        from pathlib import Path

        template = Path("web/templates/solver/solve_modal.html").read_text()
        assert "Escape" in template

    def test_modal_no_inline_onclick(self):
        """Solve modal uses event listeners instead of inline onclick."""
        from pathlib import Path

        template = Path("web/templates/solver/solve_modal.html").read_text()
        assert "onclick=" not in template
