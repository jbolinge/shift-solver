"""Forms for the shift-solver web UI."""

import json

from django import forms

from core.models import (
    ConstraintConfig,
    ScheduleRequest,
    ShiftType,
    SolverSettings,
    Worker,
    WorkerRequest,
)


class ConstraintConfigForm(forms.ModelForm):
    """ModelForm for editing ConstraintConfig instances."""

    parameters = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm font-mono",
                "rows": 3,
                "placeholder": "{}",
            }
        ),
        required=False,
    )

    class Meta:
        model = ConstraintConfig
        fields = ["enabled", "is_hard", "weight", "parameters"]
        widgets = {
            "enabled": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500",
                }
            ),
            "is_hard": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500",
                }
            ),
            "weight": forms.NumberInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
                    "min": "0",
                }
            ),
        }

    def clean_parameters(self) -> dict:
        """Validate that parameters is valid JSON."""
        raw = self.cleaned_data.get("parameters", "")
        if not raw or raw.strip() == "":
            return {}
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as err:
            raise forms.ValidationError("Parameters must be valid JSON.") from err
        if not isinstance(parsed, dict):
            raise forms.ValidationError("Parameters must be a JSON object.")
        return parsed


class WorkerForm(forms.ModelForm):
    """ModelForm for creating and editing Worker instances."""

    restricted_shifts = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm font-mono",
                "rows": 2,
                "placeholder": '["night", "weekend"]',
            }
        ),
        required=False,
        help_text="JSON list of shift type IDs this worker cannot work.",
    )

    preferred_shifts = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm font-mono",
                "rows": 2,
                "placeholder": '["day", "morning"]',
            }
        ),
        required=False,
        help_text="JSON list of shift type IDs this worker prefers.",
    )

    attributes = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm font-mono",
                "rows": 2,
                "placeholder": '{"specialty": "cardiology"}',
            }
        ),
        required=False,
        help_text="JSON object of worker attributes.",
    )

    class Meta:
        model = Worker
        fields = [
            "worker_id",
            "name",
            "email",
            "group",
            "worker_type",
            "fte",
            "is_active",
            "restricted_shifts",
            "preferred_shifts",
            "attributes",
        ]
        widgets = {
            "worker_id": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
                    "placeholder": "e.g. W001",
                }
            ),
            "name": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
                    "placeholder": "Full name",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
                    "placeholder": "email@example.com",
                }
            ),
            "group": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
                    "placeholder": "e.g. Team A",
                }
            ),
            "worker_type": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
                    "placeholder": "e.g. full_time",
                }
            ),
            "fte": forms.NumberInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
                    "step": "0.1",
                    "min": "0",
                    "max": "1",
                }
            ),
            "is_active": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.initial["restricted_shifts"] = json.dumps(
                self.instance.restricted_shifts or []
            )
            self.initial["preferred_shifts"] = json.dumps(
                self.instance.preferred_shifts or []
            )
            self.initial["attributes"] = json.dumps(
                self.instance.attributes or {}, indent=2
            )

    def clean_restricted_shifts(self) -> list:
        raw = self.cleaned_data.get("restricted_shifts", "")
        if not raw or raw.strip() == "":
            return []
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as err:
            raise forms.ValidationError("Must be valid JSON.") from err
        if not isinstance(parsed, list):
            raise forms.ValidationError("Must be a JSON list.")
        return parsed

    def clean_preferred_shifts(self) -> list:
        raw = self.cleaned_data.get("preferred_shifts", "")
        if not raw or raw.strip() == "":
            return []
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as err:
            raise forms.ValidationError("Must be valid JSON.") from err
        if not isinstance(parsed, list):
            raise forms.ValidationError("Must be a JSON list.")
        return parsed

    def clean_attributes(self) -> dict:
        raw = self.cleaned_data.get("attributes", "")
        if not raw or raw.strip() == "":
            return {}
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as err:
            raise forms.ValidationError("Must be valid JSON.") from err
        if not isinstance(parsed, dict):
            raise forms.ValidationError("Must be a JSON object.")
        return parsed


DAY_CHOICES = [
    (0, "Monday"),
    (1, "Tuesday"),
    (2, "Wednesday"),
    (3, "Thursday"),
    (4, "Friday"),
    (5, "Saturday"),
    (6, "Sunday"),
]


class ShiftTypeForm(forms.ModelForm):
    """ModelForm for creating and editing ShiftType instances."""

    applicable_days = forms.MultipleChoiceField(
        choices=DAY_CHOICES,
        widget=forms.CheckboxSelectMultiple(
            attrs={
                "class": "h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500",
            }
        ),
        required=False,
        help_text="Days of the week this shift applies to. Leave empty for all days.",
    )

    required_attributes = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm font-mono",
                "rows": 2,
                "placeholder": '{"specialty": "cardiology"}',
            }
        ),
        required=False,
        help_text="JSON object of required worker attributes.",
    )

    class Meta:
        model = ShiftType
        fields = [
            "shift_type_id",
            "name",
            "category",
            "start_time",
            "duration_hours",
            "min_workers",
            "max_workers",
            "workers_required",
            "is_undesirable",
            "is_active",
            "applicable_days",
            "required_attributes",
        ]
        widgets = {
            "shift_type_id": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
                    "placeholder": "e.g. DAY",
                }
            ),
            "name": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
                    "placeholder": "e.g. Day Shift",
                }
            ),
            "category": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
                    "placeholder": "e.g. Regular",
                }
            ),
            "start_time": forms.TimeInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
                    "type": "time",
                }
            ),
            "duration_hours": forms.NumberInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
                    "step": "0.5",
                    "min": "0",
                }
            ),
            "min_workers": forms.NumberInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
                    "min": "0",
                }
            ),
            "max_workers": forms.NumberInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
                    "min": "0",
                }
            ),
            "workers_required": forms.NumberInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
                    "min": "0",
                }
            ),
            "is_undesirable": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500",
                }
            ),
            "is_active": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if self.instance.applicable_days is not None:
                self.initial["applicable_days"] = [
                    str(d) for d in self.instance.applicable_days
                ]
            self.initial["required_attributes"] = json.dumps(
                self.instance.required_attributes or {}, indent=2
            )

    def clean_applicable_days(self) -> list[int] | None:
        raw = self.cleaned_data.get("applicable_days", [])
        if not raw:
            return None
        return [int(d) for d in raw]

    def clean_required_attributes(self) -> dict:
        raw = self.cleaned_data.get("required_attributes", "")
        if not raw or raw.strip() == "":
            return {}
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as err:
            raise forms.ValidationError("Must be valid JSON.") from err
        if not isinstance(parsed, dict):
            raise forms.ValidationError("Must be a JSON object.")
        return parsed


class ScheduleRequestForm(forms.ModelForm):
    """ModelForm for creating and editing ScheduleRequest instances."""

    class Meta:
        model = ScheduleRequest
        fields = [
            "name",
            "start_date",
            "end_date",
            "period_length_days",
            "workers",
            "shift_types",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
                    "placeholder": "e.g. March 2026 Schedule",
                }
            ),
            "start_date": forms.DateInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
                    "type": "date",
                }
            ),
            "end_date": forms.DateInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
                    "type": "date",
                }
            ),
            "period_length_days": forms.NumberInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
                    "min": "1",
                }
            ),
            "workers": forms.CheckboxSelectMultiple(
                attrs={
                    "class": "h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500",
                }
            ),
            "shift_types": forms.CheckboxSelectMultiple(
                attrs={
                    "class": "h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500",
                }
            ),
        }
        labels = {
            "period_length_days": "Period length (days)",
        }
        help_texts = {
            "period_length_days": (
                "Number of days per scheduling period (e.g., 7 for weekly, "
                "14 for biweekly, 28\u201331 for monthly). The schedule spans "
                "from Start Date to End Date; this controls how that range "
                "is divided into optimization periods."
            ),
            "workers": "Leave empty to include all active workers.",
            "shift_types": "Leave empty to include all active shift types.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["workers"].queryset = Worker.objects.filter(is_active=True)
        self.fields["shift_types"].queryset = ShiftType.objects.filter(is_active=True)
        self.fields["workers"].required = False
        self.fields["shift_types"].required = False

    def clean(self) -> dict:
        """Validate that end_date >= start_date."""
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        if start_date and end_date and end_date < start_date:
            self.add_error(
                "end_date", "End date must be on or after start date."
            )
        return cleaned_data


class SolverSettingsForm(forms.ModelForm):
    """ModelForm for editing SolverSettings instances."""

    class Meta:
        model = SolverSettings
        fields = [
            "time_limit_seconds",
            "num_search_workers",
            "optimality_tolerance",
            "log_search_progress",
        ]
        widgets = {
            "time_limit_seconds": forms.NumberInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
                    "min": "1",
                }
            ),
            "num_search_workers": forms.NumberInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
                    "min": "1",
                }
            ),
            "optimality_tolerance": forms.NumberInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
                    "step": "0.01",
                    "min": "0",
                }
            ),
            "log_search_progress": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500",
                }
            ),
        }

    def clean_time_limit_seconds(self) -> int:
        """Reject time limit values that are zero or negative."""
        value = self.cleaned_data.get("time_limit_seconds")
        if value is not None and value <= 0:
            raise forms.ValidationError("Time limit must be greater than zero.")
        return value


IS_HARD_CHOICES = [
    ("", "Use global config"),
    ("true", "Hard"),
    ("false", "Soft"),
]


class WorkerRequestForm(forms.ModelForm):
    """ModelForm for creating and editing WorkerRequest instances."""

    is_hard = forms.ChoiceField(
        choices=IS_HARD_CHOICES,
        required=False,
        widget=forms.Select(
            attrs={
                "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
            },
        ),
    )

    class Meta:
        model = WorkerRequest
        fields = [
            "worker",
            "shift_type",
            "start_date",
            "end_date",
            "request_type",
            "priority",
            "is_hard",
        ]
        widgets = {
            "worker": forms.Select(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
                }
            ),
            "shift_type": forms.Select(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
                }
            ),
            "start_date": forms.DateInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
                    "type": "date",
                }
            ),
            "end_date": forms.DateInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
                    "type": "date",
                }
            ),
            "request_type": forms.Select(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
                }
            ),
            "priority": forms.NumberInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm",
                    "min": "1",
                }
            ),
        }

    def __init__(self, *args, schedule_request=None, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            value = self.instance.is_hard
            if value is True:
                self.initial["is_hard"] = "true"
            elif value is False:
                self.initial["is_hard"] = "false"
            else:
                self.initial["is_hard"] = ""
        if schedule_request is not None:
            if schedule_request.workers.exists():
                self.fields["worker"].queryset = schedule_request.workers.all()
            if schedule_request.shift_types.exists():
                self.fields["shift_type"].queryset = schedule_request.shift_types.all()

    def clean_is_hard(self) -> bool | None:
        """Convert form string values to model values."""
        value = self.cleaned_data.get("is_hard", "")
        if value == "true":
            return True
        elif value == "false":
            return False
        return None

    def clean(self) -> dict:
        """Validate that end_date >= start_date."""
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        if start_date and end_date and end_date < start_date:
            self.add_error(
                "end_date", "End date must be on or after start date."
            )
        return cleaned_data
