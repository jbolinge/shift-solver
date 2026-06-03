"""Constraint configuration views with HTMX support."""

import json

from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from core.forms import ConstraintConfigForm
from core.models import ConstraintConfig

# Default constraint types with their configurations.
DEFAULT_CONSTRAINTS: list[dict] = [
    {
        "constraint_type": "coverage",
        "is_hard": True,
        "weight": 100,
        "description": "Ensure minimum staffing levels are met for each shift.",
    },
    {
        "constraint_type": "restriction",
        "is_hard": True,
        "weight": 100,
        "description": "Enforce worker restrictions on specific shifts.",
    },
    {
        "constraint_type": "availability",
        "is_hard": True,
        "weight": 100,
        "description": "Respect worker availability declarations.",
    },
    {
        "constraint_type": "fairness",
        "is_hard": False,
        "weight": 1000,
        "description": "Distribute shifts fairly among workers.",
    },
    {
        "constraint_type": "frequency",
        "is_hard": False,
        "weight": 100,
        "description": "Limit how often a worker is assigned certain shifts.",
    },
    {
        "constraint_type": "request",
        "is_hard": False,
        "weight": 150,
        "description": "Honor worker shift requests when possible.",
    },
    {
        "constraint_type": "sequence",
        "is_hard": False,
        "weight": 100,
        "description": "Control shift sequencing patterns for workers.",
    },
    {
        "constraint_type": "max_absence",
        "is_hard": False,
        "weight": 100,
        "description": "Limit maximum consecutive days off.",
    },
    {
        "constraint_type": "shift_frequency",
        "is_hard": False,
        "weight": 500,
        "description": "Per-worker shift frequency requirements. Configure requirements via JSON parameters.",
    },
    {
        "constraint_type": "shift_order_preference",
        "is_hard": False,
        "weight": 200,
        "description": "Preferred shift transitions between adjacent periods. Configure rules via JSON parameters.",
    },
]


# Per-constraint help text describing the accepted `parameters` JSON schema.
# These mirror the parsers in src/shift_solver/config/schema.py and the
# constraint implementations exactly.
PARAMETER_HELP: dict[str, str] = {
    "fairness": (
        'Optional: {"categories": ["weekend", "night"]} to limit fairness to '
        "specific shift categories. Default: all undesirable shifts."
    ),
    "frequency": (
        'Optional: {"max_periods_between": 4, "shift_types": ["day"]}. '
        "max_periods_between sets the window size; shift_types limits scope "
        "(default: all)."
    ),
    "sequence": (
        'Optional: {"categories": ["ambulatory"]} to limit which categories are '
        "checked for consecutive assignments. Default: all."
    ),
    "max_absence": (
        'Optional: {"max_periods_absent": 8, "shift_types": ["day"]}. '
        "max_periods_absent sets the window size; shift_types limits scope "
        "(default: all)."
    ),
    "shift_frequency": (
        'Required: {"requirements": [{"worker_id": "W001", '
        '"shift_types": ["day", "evening"], "max_periods_between": 4}]}. '
        "Each worker must work one of shift_types at least every "
        "max_periods_between periods."
    ),
    "shift_order_preference": (
        'Required: {"rules": [{"rule_id": "r1", "trigger_type": '
        '"shift_type|category|unavailability", "trigger_value": "weekend", '
        '"direction": "after|before", "preferred_type": "shift_type|category", '
        '"preferred_value": "night", "priority": 1, "worker_ids": ["W001"]}]}. '
        "worker_ids is optional (default: all workers)."
    ),
}


def _is_htmx(request: HttpRequest) -> bool:
    """Check if the request was made via HTMX."""
    return request.headers.get("HX-Request") == "true"


def constraint_list(request: HttpRequest) -> HttpResponse:
    """List all constraint configurations."""
    constraints = ConstraintConfig.objects.all()
    return render(
        request,
        "constraints/constraint_list.html",
        {"constraints": constraints},
    )


def constraint_update(request: HttpRequest, pk: int) -> HttpResponse:
    """Update a constraint's configuration."""
    constraint = get_object_or_404(ConstraintConfig, pk=pk)

    if request.method == "POST":
        # Pre-fill the parameters field with JSON string for the form
        data = request.POST.copy()
        if "parameters" not in data or data["parameters"].strip() == "":
            data["parameters"] = json.dumps(constraint.parameters)

        form = ConstraintConfigForm(data, instance=constraint)
        if form.is_valid():
            constraint = form.save()
            if _is_htmx(request):
                return render(
                    request,
                    "constraints/constraint_row.html",
                    {"constraint": constraint},
                )
            return redirect("constraint-list")
    else:
        # Pre-populate parameters as JSON string
        initial = {"parameters": json.dumps(constraint.parameters, indent=2)}
        form = ConstraintConfigForm(instance=constraint, initial=initial)

    template = "constraints/constraint_form.html"
    context = {
        "form": form,
        "constraint": constraint,
        "parameters_help": PARAMETER_HELP.get(constraint.constraint_type, ""),
    }
    if _is_htmx(request):
        return render(request, template, context)
    return render(request, template, context)


def constraint_seed(request: HttpRequest) -> HttpResponse:
    """Seed default constraint configurations."""
    if request.method == "POST":
        for defaults in DEFAULT_CONSTRAINTS:
            ConstraintConfig.objects.get_or_create(
                constraint_type=defaults["constraint_type"],
                defaults={
                    "enabled": True,
                    "is_hard": defaults["is_hard"],
                    "weight": defaults["weight"],
                    "description": defaults["description"],
                    "parameters": {},
                },
            )
        return redirect("constraint-list")

    return redirect("constraint-list")
