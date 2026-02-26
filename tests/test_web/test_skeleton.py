"""Tests for Django project skeleton (scheduler-110)."""

import pytest

pytestmark = pytest.mark.django_db


class TestDjangoSkeleton:
    """Test that the Django project skeleton is correctly configured."""

    def test_django_settings_importable(self) -> None:
        """Django settings module can be imported without error."""
        from django.conf import settings

        assert settings.configured
        assert isinstance(settings.DEBUG, bool)

    def test_django_check_passes(self) -> None:
        """Django system check passes with no critical issues."""
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        # call_command raises SystemCheckError if there are critical issues
        call_command("check", stdout=out)
        output = out.getvalue()
        assert "no issues" in output.lower() or "System check" in output

    def test_django_urls_importable(self) -> None:
        """Root URL configuration can be imported."""
        from django.urls import reverse

        # The admin URL should be resolvable
        url = reverse("admin:index")
        assert url == "/admin/"

    def test_core_app_config_exists(self) -> None:
        """Core app has a valid AppConfig."""
        from django.apps import apps

        core_config = apps.get_app_config("core")
        assert core_config is not None
        assert core_config.name == "core"

    def test_static_files_configured(self) -> None:
        """STATIC_URL and STATICFILES_DIRS are configured."""
        from django.conf import settings

        assert settings.STATIC_URL is not None
        assert hasattr(settings, "STATICFILES_DIRS")

    def test_templates_configured(self) -> None:
        """Template directories are configured."""
        from django.conf import settings

        assert len(settings.TEMPLATES) > 0
        template_config = settings.TEMPLATES[0]
        assert template_config["BACKEND"] == "django.template.backends.django.DjangoTemplates"
        assert len(template_config["DIRS"]) > 0

    def test_database_configured(self) -> None:
        """Database is configured as SQLite."""
        from django.conf import settings

        db = settings.DATABASES["default"]
        assert "sqlite3" in db["ENGINE"]

    def test_default_auto_field(self) -> None:
        """DEFAULT_AUTO_FIELD is set to BigAutoField."""
        from django.conf import settings

        assert settings.DEFAULT_AUTO_FIELD == "django.db.models.BigAutoField"
