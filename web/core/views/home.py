"""Home/dashboard view."""

from django.views.generic import TemplateView

from core.models import ConstraintConfig, ScheduleRequest, ShiftType, SolverRun, Worker


class HomeView(TemplateView):
    """Dashboard home page showing summary counts."""

    template_name = "home.html"

    def get_context_data(self, **kwargs):  # type: ignore[override]
        context = super().get_context_data(**kwargs)
        context["worker_count"] = Worker.objects.filter(is_active=True).count()
        context["shift_type_count"] = ShiftType.objects.filter(is_active=True).count()
        context["request_count"] = ScheduleRequest.objects.count()
        context["constraint_count"] = ConstraintConfig.objects.count()
        context["recent_requests"] = ScheduleRequest.objects.order_by("-created_at")[:5]
        context["recent_runs"] = SolverRun.objects.order_by("-started_at")[:3]
        return context
