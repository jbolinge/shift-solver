"""Forms for the shift-solver web UI."""

from django import forms

from core.models import ScheduleRequest, ShiftType, Worker


class WorkerForm(forms.ModelForm):
    """ModelForm for creating and editing Worker instances."""

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


class ShiftTypeForm(forms.ModelForm):
    """ModelForm for creating and editing ShiftType instances."""

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


class ScheduleRequestForm(forms.ModelForm):
    """ModelForm for creating and editing ScheduleRequest instances."""

    class Meta:
        model = ScheduleRequest
        fields = [
            "name",
            "start_date",
            "end_date",
            "period_length_days",
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
        }

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
