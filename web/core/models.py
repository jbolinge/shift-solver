"""Django ORM models for the shift-solver web UI."""

from django.db import models


class Worker(models.Model):
    """A schedulable resource (employee, contractor, etc.)."""

    worker_id = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    email = models.EmailField(blank=True, default="")
    group = models.CharField(max_length=100, blank=True, default="")
    worker_type = models.CharField(max_length=100, blank=True, default="")
    fte = models.FloatField(default=1.0)
    is_active = models.BooleanField(default=True)
    restricted_shifts = models.JSONField(default=list, blank=True)
    preferred_shifts = models.JSONField(default=list, blank=True)
    attributes = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return str(self.name)


class ShiftType(models.Model):
    """A type of shift with time, duration, and requirements."""

    shift_type_id = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=100, blank=True, default="")
    start_time = models.TimeField()
    duration_hours = models.FloatField()
    is_undesirable = models.BooleanField(default=False)
    min_workers = models.IntegerField(default=1)
    max_workers = models.IntegerField(null=True, blank=True)
    workers_required = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)
    applicable_days = models.JSONField(null=True, blank=True)
    required_attributes = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return str(self.name)


class Availability(models.Model):
    """Worker availability for a specific date/shift."""

    worker = models.ForeignKey(
        Worker, on_delete=models.CASCADE, related_name="availabilities"
    )
    date = models.DateField()
    shift_type = models.ForeignKey(
        ShiftType, on_delete=models.CASCADE, null=True, blank=True
    )
    is_available = models.BooleanField(default=True)
    preference = models.IntegerField(default=0)  # -1=avoid, 0=neutral, 1=prefer

    class Meta:
        ordering = ["date"]

    def __str__(self) -> str:
        status = "Available" if self.is_available else "Unavailable"
        return f"{self.worker} - {self.date} ({status})"


class ConstraintConfig(models.Model):
    """Configuration for a scheduling constraint."""

    constraint_type = models.CharField(max_length=100, unique=True)
    enabled = models.BooleanField(default=True)
    is_hard = models.BooleanField(default=True)
    weight = models.IntegerField(default=1)
    parameters = models.JSONField(default=dict, blank=True)
    description = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["constraint_type"]

    def __str__(self) -> str:
        return str(self.constraint_type)


class ScheduleRequest(models.Model):
    """A request to generate a schedule for a date range."""

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    name = models.CharField(max_length=200)
    start_date = models.DateField()
    end_date = models.DateField()
    period_length_days = models.IntegerField(default=7)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    workers = models.ManyToManyField(Worker, blank=True)
    shift_types = models.ManyToManyField(ShiftType, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return str(self.name)


class SolverSettings(models.Model):
    """Solver configuration parameters for a schedule request."""

    schedule_request = models.OneToOneField(
        ScheduleRequest, on_delete=models.CASCADE, related_name="solver_settings"
    )
    time_limit_seconds = models.IntegerField(default=60)
    num_search_workers = models.IntegerField(default=8)
    optimality_tolerance = models.FloatField(default=0.0)
    log_search_progress = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "solver settings"

    def __str__(self) -> str:
        return f"Settings for {self.schedule_request}"


class SolverRun(models.Model):
    """Tracks a solver execution."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    schedule_request = models.ForeignKey(
        ScheduleRequest, on_delete=models.CASCADE, related_name="solver_runs"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    result_json = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")
    progress_percent = models.IntegerField(default=0)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"Run #{self.pk} - {self.status}"


class Assignment(models.Model):
    """A worker assigned to a shift on a specific date."""

    solver_run = models.ForeignKey(
        SolverRun, on_delete=models.CASCADE, related_name="assignments"
    )
    worker = models.ForeignKey(Worker, on_delete=models.CASCADE)
    shift_type = models.ForeignKey(ShiftType, on_delete=models.CASCADE)
    date = models.DateField()

    class Meta:
        ordering = ["date", "worker"]

    def __str__(self) -> str:
        return f"{self.worker} - {self.shift_type} on {self.date}"
