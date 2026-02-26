"""Core app configuration."""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Configuration for the core scheduling app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
