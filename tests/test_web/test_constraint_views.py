"""Tests for Constraint configuration views with HTMX support."""

import json

import pytest
from django.test import Client

from core.models import ConstraintConfig

pytestmark = pytest.mark.django_db


class TestConstraintListView:
    """Tests for the constraint list view."""

    def test_constraint_list_returns_200(self, client: Client) -> None:
        """GET /constraints/ returns HTTP 200."""
        response = client.get("/constraints/")
        assert response.status_code == 200

    def test_constraint_list_shows_all_constraints(self, client: Client) -> None:
        """Constraint list displays all configured constraints."""
        ConstraintConfig.objects.create(
            constraint_type="coverage",
            enabled=True,
            is_hard=True,
            weight=100,
            description="Ensure minimum staffing",
        )
        ConstraintConfig.objects.create(
            constraint_type="fairness",
            enabled=True,
            is_hard=False,
            weight=1000,
            description="Distribute shifts fairly",
        )
        ConstraintConfig.objects.create(
            constraint_type="frequency",
            enabled=False,
            is_hard=False,
            weight=100,
            description="Limit shift frequency",
        )

        response = client.get("/constraints/")
        content = response.content.decode()

        assert "coverage" in content
        assert "fairness" in content
        assert "frequency" in content

    def test_constraint_list_shows_enabled_status(self, client: Client) -> None:
        """Constraint list shows enabled/disabled status for each constraint."""
        ConstraintConfig.objects.create(
            constraint_type="coverage",
            enabled=True,
            is_hard=True,
            weight=100,
        )
        ConstraintConfig.objects.create(
            constraint_type="fairness",
            enabled=False,
            is_hard=False,
            weight=1000,
        )

        response = client.get("/constraints/")
        content = response.content.decode()

        assert "Enabled" in content
        assert "Disabled" in content


class TestConstraintUpdateView:
    """Tests for the constraint update view."""

    def test_toggle_constraint_enabled(self, client: Client) -> None:
        """POST to toggle enabled status switches constraint on/off."""
        constraint = ConstraintConfig.objects.create(
            constraint_type="coverage",
            enabled=True,
            is_hard=True,
            weight=100,
        )

        response = client.post(
            f"/constraints/{constraint.pk}/edit/",
            {"enabled": "", "is_hard": "on", "weight": "100", "parameters": "{}"},
        )

        constraint.refresh_from_db()
        assert constraint.enabled is False
        assert response.status_code in (200, 302)

    def test_toggle_hard_soft(self, client: Client) -> None:
        """POST to switch is_hard flag between hard and soft."""
        constraint = ConstraintConfig.objects.create(
            constraint_type="fairness",
            enabled=True,
            is_hard=True,
            weight=1000,
        )

        response = client.post(
            f"/constraints/{constraint.pk}/edit/",
            {"enabled": "on", "is_hard": "", "weight": "1000", "parameters": "{}"},
        )

        constraint.refresh_from_db()
        assert constraint.is_hard is False
        assert response.status_code in (200, 302)

    def test_update_weight(self, client: Client) -> None:
        """POST to change weight value updates the constraint."""
        constraint = ConstraintConfig.objects.create(
            constraint_type="fairness",
            enabled=True,
            is_hard=False,
            weight=100,
        )

        response = client.post(
            f"/constraints/{constraint.pk}/edit/",
            {"enabled": "on", "is_hard": "", "weight": "500", "parameters": "{}"},
        )

        constraint.refresh_from_db()
        assert constraint.weight == 500
        assert response.status_code in (200, 302)

    def test_update_parameters(self, client: Client) -> None:
        """POST to update parameters JSON saves new parameters."""
        constraint = ConstraintConfig.objects.create(
            constraint_type="fairness",
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={},
        )

        new_params = json.dumps({"max_diff": 3})
        response = client.post(
            f"/constraints/{constraint.pk}/edit/",
            {
                "enabled": "on",
                "is_hard": "",
                "weight": "100",
                "parameters": new_params,
            },
        )

        constraint.refresh_from_db()
        assert constraint.parameters == {"max_diff": 3}
        assert response.status_code in (200, 302)


class TestConstraintSeedView:
    """Tests for the constraint seed view."""

    def test_seed_creates_default_constraints(self, client: Client) -> None:
        """POST /constraints/seed/ creates entries for all known constraint types."""
        assert ConstraintConfig.objects.count() == 0

        response = client.post("/constraints/seed/")
        assert response.status_code == 302

        assert ConstraintConfig.objects.count() == 8

        expected_types = {
            "coverage",
            "restriction",
            "availability",
            "fairness",
            "frequency",
            "request",
            "sequence",
            "max_absence",
        }
        actual_types = set(
            ConstraintConfig.objects.values_list("constraint_type", flat=True)
        )
        assert actual_types == expected_types

        # Verify hard constraints
        for ct in ("coverage", "restriction", "availability"):
            c = ConstraintConfig.objects.get(constraint_type=ct)
            assert c.is_hard is True
            assert c.weight == 100

        # Verify soft constraints
        fairness = ConstraintConfig.objects.get(constraint_type="fairness")
        assert fairness.is_hard is False
        assert fairness.weight == 1000

    def test_seed_idempotent(self, client: Client) -> None:
        """Seeding twice does not duplicate constraints."""
        client.post("/constraints/seed/")
        assert ConstraintConfig.objects.count() == 8

        client.post("/constraints/seed/")
        assert ConstraintConfig.objects.count() == 8
