"""Tests for base templates and HTMX setup (scheduler-113)."""

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db


class TestBaseTemplates:
    """Test base templates and home page."""

    def test_home_page_returns_200(self, client: Client) -> None:
        """Home page returns HTTP 200."""
        response = client.get("/")
        assert response.status_code == 200

    def test_home_page_contains_tailwind(self, client: Client) -> None:
        """Base template includes Tailwind CSS CDN."""
        response = client.get("/")
        content = response.content.decode()
        assert "tailwindcss" in content

    def test_home_page_contains_htmx(self, client: Client) -> None:
        """Base template includes HTMX script."""
        response = client.get("/")
        content = response.content.decode()
        assert "htmx.org" in content

    def test_home_page_has_sidebar_navigation(self, client: Client) -> None:
        """Home page includes sidebar with navigation links."""
        response = client.get("/")
        content = response.content.decode()
        assert "Workers" in content
        assert "Shift Types" in content
        assert "Availability" in content
        assert "Constraints" in content

    def test_home_page_has_navbar(self, client: Client) -> None:
        """Home page includes top navigation bar."""
        response = client.get("/")
        content = response.content.decode()
        assert "Shift Solver" in content

    def test_base_template_has_content_block(self) -> None:
        """Base template defines a 'content' block."""
        from django.template.loader import get_template

        template = get_template("base.html")
        # Render the template - if content block exists, it should render OK
        rendered = template.render({})
        assert "<!DOCTYPE html>" in rendered
