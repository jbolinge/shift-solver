"""Tests for production fail-fast behavior and security flags in Django settings."""

import importlib
import os
from collections.abc import Callable
from types import ModuleType
from unittest import mock

import pytest
from django.core.exceptions import ImproperlyConfigured

import config.settings as settings_module

ENV_KEYS = (
    "DJANGO_DEBUG",
    "DJANGO_SECRET_KEY",
    "DJANGO_ALLOWED_HOSTS",
    "DJANGO_SECURE_SSL_REDIRECT",
    "DJANGO_SECURE_HSTS_SECONDS",
    "MAX_IMPORT_FILE_SIZE",
)


@pytest.fixture
def reload_settings() -> Callable[..., ModuleType]:
    """Reload config.settings under a controlled environment.

    The module is re-imported with the real environment on teardown so other
    tests see the original settings module state.
    """

    conditional_attrs = (
        "SESSION_COOKIE_SECURE",
        "CSRF_COOKIE_SECURE",
        "SECURE_SSL_REDIRECT",
        "SECURE_HSTS_SECONDS",
        "SECURE_HSTS_INCLUDE_SUBDOMAINS",
    )

    def _reload(**env: str) -> ModuleType:
        # reload() re-executes the module in its existing namespace, so
        # attributes set only in production mode would otherwise linger.
        for attr in conditional_attrs:
            settings_module.__dict__.pop(attr, None)
        clean = {k: v for k, v in os.environ.items() if k not in ENV_KEYS}
        clean.update(env)
        with mock.patch.dict(os.environ, clean, clear=True):
            return importlib.reload(settings_module)

    yield _reload
    importlib.reload(settings_module)


def test_dev_defaults_without_env(reload_settings) -> None:
    s = reload_settings()
    assert s.DEBUG is True
    assert s.ALLOWED_HOSTS == ["localhost", "127.0.0.1", "[::1]"]
    assert s.SECRET_KEY.startswith("django-insecure")
    assert s.MAX_IMPORT_FILE_SIZE == 5 * 1024 * 1024


def test_production_requires_secret_key(reload_settings) -> None:
    with pytest.raises(ImproperlyConfigured, match="DJANGO_SECRET_KEY"):
        reload_settings(DJANGO_DEBUG="false")


def test_production_requires_allowed_hosts(reload_settings) -> None:
    with pytest.raises(ImproperlyConfigured, match="DJANGO_ALLOWED_HOSTS"):
        reload_settings(DJANGO_DEBUG="false", DJANGO_SECRET_KEY="prod-key")


def test_production_configuration(reload_settings) -> None:
    s = reload_settings(
        DJANGO_DEBUG="false",
        DJANGO_SECRET_KEY="prod-key",
        DJANGO_ALLOWED_HOSTS="example.com, www.example.com",
    )
    assert s.DEBUG is False
    assert s.SECRET_KEY == "prod-key"
    assert s.ALLOWED_HOSTS == ["example.com", "www.example.com"]
    assert s.SESSION_COOKIE_SECURE is True
    assert s.CSRF_COOKIE_SECURE is True
    assert s.SECURE_SSL_REDIRECT is True
    assert s.SECURE_HSTS_SECONDS == 3600
    assert s.SECURE_CONTENT_TYPE_NOSNIFF is True


def test_production_ssl_redirect_can_be_disabled(reload_settings) -> None:
    s = reload_settings(
        DJANGO_DEBUG="false",
        DJANGO_SECRET_KEY="prod-key",
        DJANGO_ALLOWED_HOSTS="example.com",
        DJANGO_SECURE_SSL_REDIRECT="false",
    )
    assert s.SECURE_SSL_REDIRECT is False


def test_dev_does_not_force_secure_cookies(reload_settings) -> None:
    s = reload_settings()
    assert not hasattr(s, "SESSION_COOKIE_SECURE")
    assert not hasattr(s, "CSRF_COOKIE_SECURE")
