"""Constraint configuration views with HTMX support."""

import json
from typing import Any

from django.http import HttpRequest, HttpResponse, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from pydantic import ValidationError

from core.forms import ConstraintConfigForm
from core.models import ConstraintConfig
from shift_solver.config.schema import (
    parse_shift_frequency_requirements,
    parse_shift_order_preferences,
)

# Constraint types that use a structured row editor instead of the raw JSON
# textarea. Their parameters are assembled server-side from posted row fields
# and validated with the same parsers the solver uses.
STRUCTURED_CONSTRAINTS = ("shift_frequency", "shift_order_preference")

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
        "description": "Per-worker shift frequency requirements. Configure requirements in the editor.",
    },
    {
        "constraint_type": "shift_order_preference",
        "is_hard": False,
        "weight": 200,
        "description": "Preferred shift transitions between adjacent periods. Configure rules in the editor.",
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


def _split_csv(raw: str) -> list[str]:
    """Split a comma-separated input into a list of trimmed, non-empty values."""
    return [part.strip() for part in raw.split(",") if part.strip()]


# POST field names for each structured editor's repeatable rows, in order.
_SF_FIELDS = ("req_worker_id", "req_shift_types", "req_max_periods")
_SOP_FIELDS = (
    "rule_id",
    "rule_trigger_type",
    "rule_trigger_value",
    "rule_direction",
    "rule_preferred_type",
    "rule_preferred_value",
    "rule_priority",
    "rule_worker_ids",
)


def _zip_post(post: QueryDict, *keys: str):
    """Yield parallel POST list fields one row at a time."""
    return zip(*(post.getlist(key) for key in keys), strict=False)


def _sf_rows_from_params(parameters: dict | None) -> list[dict[str, Any]]:
    """Build template rows from a saved shift_frequency parameters dict."""
    rows = []
    for req in (parameters or {}).get("requirements", []):
        rows.append(
            {
                "worker_id": req.get("worker_id", ""),
                "shift_types": ", ".join(req.get("shift_types", [])),
                "max_periods": req.get("max_periods_between", ""),
            }
        )
    return rows


def _sf_rows_from_post(post: QueryDict) -> list[dict[str, Any]]:
    """Build template rows from submitted shift_frequency row fields."""
    rows = []
    for worker_id, shift_types, max_periods in _zip_post(post, *_SF_FIELDS):
        if not (worker_id.strip() or shift_types.strip() or max_periods.strip()):
            continue
        rows.append(
            {
                "worker_id": worker_id,
                "shift_types": shift_types,
                "max_periods": max_periods,
            }
        )
    return rows


def _sf_build_parameters(post: QueryDict) -> dict[str, Any]:
    """Assemble (and validate) shift_frequency parameters from posted rows.

    Raises ValueError on non-numeric max_periods and ValidationError on data
    that fails the engine's own parser.
    """
    requirements = []
    for worker_id, shift_types, max_periods in _zip_post(post, *_SF_FIELDS):
        worker_id = worker_id.strip()
        shift_type_list = _split_csv(shift_types)
        max_periods = max_periods.strip()
        if not (worker_id or shift_type_list or max_periods):
            continue
        requirements.append(
            {
                "worker_id": worker_id,
                "shift_types": shift_type_list,
                "max_periods_between": int(max_periods) if max_periods else 0,
            }
        )
    parameters = {"requirements": requirements}
    # Validate using the exact parser the solver uses; raises on bad data.
    parse_shift_frequency_requirements(parameters)
    return parameters


def _sop_rows_from_params(parameters: dict | None) -> list[dict[str, Any]]:
    """Build template rows from a saved shift_order_preference parameters dict."""
    rows = []
    for rule in (parameters or {}).get("rules", []):
        rows.append(
            {
                "rule_id": rule.get("rule_id", ""),
                "trigger_type": rule.get("trigger_type", "shift_type"),
                "trigger_value": rule.get("trigger_value") or "",
                "direction": rule.get("direction", "after"),
                "preferred_type": rule.get("preferred_type", "shift_type"),
                "preferred_value": rule.get("preferred_value", ""),
                "priority": rule.get("priority", 1),
                "worker_ids": ", ".join(rule.get("worker_ids") or []),
            }
        )
    return rows


def _sop_rows_from_post(post: QueryDict) -> list[dict[str, Any]]:
    """Build template rows from submitted shift_order_preference row fields."""
    rows = []
    for (
        rule_id,
        t_type,
        t_value,
        direction,
        p_type,
        p_value,
        priority,
        worker_ids,
    ) in _zip_post(post, *_SOP_FIELDS):
        if not (rule_id.strip() or p_value.strip()):
            continue
        rows.append(
            {
                "rule_id": rule_id,
                "trigger_type": t_type,
                "trigger_value": t_value,
                "direction": direction,
                "preferred_type": p_type,
                "preferred_value": p_value,
                "priority": priority,
                "worker_ids": worker_ids,
            }
        )
    return rows


def _sop_build_parameters(post: QueryDict) -> dict[str, Any]:
    """Assemble (and validate) shift_order_preference parameters from posted rows.

    Raises ValueError on non-numeric priority and ValidationError on data that
    fails the engine's own parser.
    """
    rules = []
    for (
        rule_id,
        t_type,
        t_value,
        direction,
        p_type,
        p_value,
        priority,
        worker_ids,
    ) in _zip_post(post, *_SOP_FIELDS):
        rule_id = rule_id.strip()
        p_value = p_value.strip()
        if not (rule_id or p_value):
            continue
        worker_id_list = _split_csv(worker_ids)
        rules.append(
            {
                "rule_id": rule_id,
                "trigger_type": t_type.strip(),
                "trigger_value": t_value.strip() or None,
                "direction": direction.strip(),
                "preferred_type": p_type.strip(),
                "preferred_value": p_value,
                "priority": int(priority) if priority.strip() else 1,
                "worker_ids": worker_id_list or None,
            }
        )
    parameters = {"rules": rules}
    parse_shift_order_preferences(parameters)
    return parameters


def _structured_build_parameters(
    constraint_type: str, post: QueryDict
) -> dict[str, Any]:
    """Dispatch to the right structured-parameter builder for the constraint."""
    if constraint_type == "shift_frequency":
        return _sf_build_parameters(post)
    return _sop_build_parameters(post)


def _structured_rows(
    constraint: ConstraintConfig, post: QueryDict | None
) -> dict[str, Any]:
    """Return template context rows for a structured constraint.

    Uses submitted ``post`` data when re-rendering after an error (so input is
    not lost), otherwise the saved parameters.
    """
    if constraint.constraint_type == "shift_frequency":
        rows = (
            _sf_rows_from_post(post)
            if post is not None
            else _sf_rows_from_params(constraint.parameters)
        )
    else:
        rows = (
            _sop_rows_from_post(post)
            if post is not None
            else _sop_rows_from_params(constraint.parameters)
        )
    # Always show at least one (blank) row so the fields are visible without
    # first clicking "Add". Blank rows are skipped on save.
    if not rows:
        rows = [{}]
    return {"rows": rows}


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
    is_structured = constraint.constraint_type in STRUCTURED_CONSTRAINTS
    structured_error = None

    if request.method == "POST":
        data = request.POST.copy()
        # Structured constraints assemble parameters from row fields; the JSON
        # textarea is not rendered for them, so leave parameters empty here.
        if not is_structured and (
            "parameters" not in data or data["parameters"].strip() == ""
        ):
            data["parameters"] = json.dumps(constraint.parameters)

        form = ConstraintConfigForm(data, instance=constraint)

        structured_params = None
        if is_structured:
            try:
                structured_params = _structured_build_parameters(
                    constraint.constraint_type, request.POST
                )
            except ValidationError as err:
                structured_error = "; ".join(e.get("msg", str(e)) for e in err.errors())
            except ValueError as err:
                structured_error = str(err)

        if form.is_valid() and structured_error is None:
            constraint = form.save(commit=False)
            if is_structured and structured_params is not None:
                constraint.parameters = structured_params
            constraint.save()
            if _is_htmx(request):
                return render(
                    request,
                    "constraints/constraint_row.html",
                    {"constraint": constraint},
                )
            return redirect("constraint-list")
    else:
        # Pre-populate parameters as JSON string for the generic editor
        initial = {"parameters": json.dumps(constraint.parameters, indent=2)}
        form = ConstraintConfigForm(instance=constraint, initial=initial)

    template = "constraints/constraint_form.html"
    context: dict[str, Any] = {
        "form": form,
        "constraint": constraint,
        "parameters_help": PARAMETER_HELP.get(constraint.constraint_type, ""),
        "is_structured": is_structured,
        "structured_error": structured_error,
    }
    if is_structured:
        post = request.POST if request.method == "POST" else None
        context.update(_structured_rows(constraint, post))
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
