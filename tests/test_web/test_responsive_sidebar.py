"""Tests for responsive sidebar with mobile hamburger (scheduler-133)."""

import pytest
from django.test import Client


@pytest.mark.django_db
class TestHamburgerButton:
    def test_sidebar_toggle_button_present(self, client: Client):
        """Navbar contains a sidebar toggle button."""
        response = client.get("/")
        html = response.content.decode()
        assert 'id="sidebar-toggle"' in html

    def test_toggle_button_has_aria_expanded(self, client: Client):
        """Toggle button has aria-expanded attribute."""
        response = client.get("/")
        html = response.content.decode()
        assert 'aria-expanded=' in html

    def test_toggle_button_has_aria_label(self, client: Client):
        """Toggle button has descriptive aria-label."""
        response = client.get("/")
        html = response.content.decode()
        assert 'aria-label="Toggle navigation"' in html


@pytest.mark.django_db
class TestResponsiveSidebar:
    def test_sidebar_has_id(self, client: Client):
        """Sidebar has id='sidebar' for toggle targeting."""
        response = client.get("/")
        html = response.content.decode()
        assert 'id="sidebar"' in html

    def test_sidebar_has_responsive_classes(self, client: Client):
        """Sidebar uses 'hidden md:block' for responsive behavior."""
        response = client.get("/")
        html = response.content.decode()
        assert "md:block" in html

    def test_toggle_script_present(self, client: Client):
        """Base template includes sidebar toggle script."""
        response = client.get("/")
        html = response.content.decode()
        assert "sidebar-toggle" in html
        assert "classList.toggle" in html or "classList" in html
