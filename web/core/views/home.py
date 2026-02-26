"""Home/dashboard view."""

from django.views.generic import TemplateView

from core.models import ScheduleRequest, ShiftType, Worker


class HomeView(TemplateView):
    """Dashboard home page showing summary counts."""

    template_name = "home.html"

    def get_context_data(self, **kwargs):  # type: ignore[override]
        context = super().get_context_data(**kwargs)
        context["worker_count"] = Worker.objects.filter(is_active=True).count()
        context["shift_type_count"] = ShiftType.objects.filter(is_active=True).count()
        context["request_count"] = ScheduleRequest.objects.count()
        return context
