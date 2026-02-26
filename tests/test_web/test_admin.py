"""Tests for Django admin with django-unfold (scheduler-114)."""

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db


class TestDjangoAdmin:
    """Test admin configuration."""

    def test_admin_login_page_loads(self, client: Client) -> None:
        """Admin login page returns HTTP 200."""
        response = client.get("/admin/login/")
        assert response.status_code == 200

    def test_worker_admin_registered(self) -> None:
        """Worker model is registered with admin site."""
        from django.contrib import admin

        from core.models import Worker

        assert Worker in admin.site._registry

    def test_shift_type_admin_registered(self) -> None:
        """ShiftType model is registered with admin site."""
        from django.contrib import admin

        from core.models import ShiftType

        assert ShiftType in admin.site._registry

    def test_constraint_config_admin_registered(self) -> None:
        """ConstraintConfig model is registered with admin site."""
        from django.contrib import admin

        from core.models import ConstraintConfig

        assert ConstraintConfig in admin.site._registry

    def test_schedule_request_admin_registered(self) -> None:
        """ScheduleRequest model is registered with admin site."""
        from django.contrib import admin

        from core.models import ScheduleRequest

        assert ScheduleRequest in admin.site._registry

    def test_solver_run_admin_registered(self) -> None:
        """SolverRun model is registered with admin site."""
        from django.contrib import admin

        from core.models import SolverRun

        assert SolverRun in admin.site._registry

    def test_assignment_admin_registered(self) -> None:
        """Assignment model is registered with admin site."""
        from django.contrib import admin

        from core.models import Assignment

        assert Assignment in admin.site._registry
